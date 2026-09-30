"""
Long-Horizon Autonomous Task Checkpoint & Resumption Engine (Zero External Dependencies)
Provides event-sourcing persistence, idempotency guarantees, and human-in-the-loop pause/resume.
"""
import time
import math
import hashlib
import json
from typing import Dict, Any, List, Optional

class LongHorizonAutonomousTaskResumptionEngine:
    def __init__(self, session_ttl_days: int = 14):
        self.session_ttl_sec = session_ttl_days * 86400
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.processed_idempotency_keys: Dict[str, str] = {} # key -> session_id

    def create_task_session(
        self,
        task_goal: str,
        initial_context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a persistent, resumable long-running agent task session."""
        if idempotency_key and idempotency_key in self.processed_idempotency_keys:
            existing_id = self.processed_idempotency_keys[idempotency_key]
            return self.get_session_state(existing_id)

        now = time.time()
        session_id = "TASK-SES-" + hashlib.sha256(f"{task_goal}{now}".encode("utf-8")).hexdigest()[:16]

        session = {
            "session_id": session_id,
            "task_goal": task_goal,
            "status": "RUNNING", # RUNNING, SUSPENDED_WAITING_APPROVAL, COMPLETED, FAILED
            "created_at": now,
            "last_active_at": now,
            "context": initial_context or {},
            "checkpoints": [],
            "approval_gate": None,
            "total_steps_executed": 0
        }

        self.sessions[session_id] = session
        if idempotency_key:
            self.processed_idempotency_keys[idempotency_key] = session_id

        return session

    def record_step_checkpoint(
        self,
        session_id: str,
        step_name: str,
        step_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Appends an immutable state event checkpoint to the session log."""
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        s = self.sessions[session_id]
        now = time.time()
        s["last_active_at"] = now
        s["total_steps_executed"] += 1

        checkpoint = {
            "step_index": len(s["checkpoints"]) + 1,
            "step_name": step_name,
            "timestamp": now,
            "payload": step_payload,
            "checkpoint_hash": hashlib.sha256(f"{session_id}{step_name}{now}".encode("utf-8")).hexdigest()[:16]
        }
        s["checkpoints"].append(checkpoint)

        # Merge payload into persistent context
        s["context"].update(step_payload.get("context_delta", {}))

        return {
            "session_id": session_id,
            "checkpoint_recorded": True,
            "current_step": checkpoint["step_index"],
            "checkpoint_hash": checkpoint["checkpoint_hash"]
        }

    def suspend_for_approval(
        self,
        session_id: str,
        approval_prompt: str,
        pending_action_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Suspends background task execution waiting for human-in-the-loop authorization."""
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        s = self.sessions[session_id]
        resume_token = "RSM-" + hashlib.sha256(f"{session_id}{time.time()}".encode("utf-8")).hexdigest()[:20]

        s["status"] = "SUSPENDED_WAITING_APPROVAL"
        s["approval_gate"] = {
            "prompt": approval_prompt,
            "resume_token": resume_token,
            "suspended_at": time.time(),
            "pending_action": pending_action_payload or {}
        }

        return {
            "session_id": session_id,
            "status": "SUSPENDED_WAITING_APPROVAL",
            "approval_prompt": approval_prompt,
            "resume_token": resume_token
        }

    def resume_task_session(
        self,
        session_id: str,
        resume_token: str,
        user_decision: str = "APPROVED",
        decision_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resumes a suspended task session verifying the cryptographic authorization token."""
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        s = self.sessions[session_id]
        gate = s.get("approval_gate")
        if not gate or gate.get("resume_token") != resume_token:
            return {"error": "Invalid or expired resume token"}

        now = time.time()
        s["last_active_at"] = now
        s["status"] = "RUNNING" if user_decision == "APPROVED" else "CANCELLED_BY_USER"
        s["approval_gate"] = None

        if decision_context:
            s["context"].update(decision_context)

        # Record resume checkpoint
        self.record_step_checkpoint(session_id, "USER_RESUME_GATE", {
            "decision": user_decision,
            "token": resume_token
        })

        return {
            "session_id": session_id,
            "status": s["status"],
            "resumed_successfully": user_decision == "APPROVED"
        }

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}
        return self.sessions[session_id]
