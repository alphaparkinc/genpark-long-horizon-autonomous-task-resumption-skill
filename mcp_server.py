"""MCP Server for Long-Horizon Autonomous Task Resumption Engine."""
import sys
import json
import time
from client import LongHorizonAutonomousTaskResumptionEngine

engine = LongHorizonAutonomousTaskResumptionEngine()

def handle_call_tool(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name != "manage_long_horizon_resumption":
        raise ValueError(f"Unknown tool: {name}")

    action = args.get("action", "get_session_state")
    if action == "create_task_session":
        return engine.create_task_session(
            task_goal=args.get("task_goal", "Multi-day workflow"),
            initial_context=args.get("step_payload"),
            idempotency_key=args.get("idempotency_key")
        )
    elif action == "record_step_checkpoint":
        return engine.record_step_checkpoint(
            session_id=args.get("session_id"),
            step_name=args.get("step_name", "step"),
            step_payload=args.get("step_payload", {})
        )
    elif action == "suspend_for_approval":
        return engine.suspend_for_approval(
            session_id=args.get("session_id"),
            approval_prompt=args.get("approval_prompt", "Authorize transaction?"),
            pending_action_payload=args.get("step_payload")
        )
    elif action == "resume_task_session":
        return engine.resume_task_session(
            session_id=args.get("session_id"),
            resume_token=args.get("resume_token", ""),
            user_decision="APPROVED"
        )
    elif action == "get_session_state":
        return engine.get_session_state(args.get("session_id"))
    else:
        raise ValueError(f"Invalid action: {action}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running self-test...")
        ses = engine.create_task_session("Purchase airline tickets if price drops under $800")
        assert ses["status"] == "RUNNING"
        engine.record_step_checkpoint(ses["session_id"], "MONITOR_FLIGHT_API", {"price": 850})
        sus = engine.suspend_for_approval(ses["session_id"], "Flight reached $780. Approve $780 charge?")
        assert sus["status"] == "SUSPENDED_WAITING_APPROVAL"
        res = engine.resume_task_session(ses["session_id"], sus["resume_token"], "APPROVED")
        assert res["resumed_successfully"] is True
        print("Self-test PASSED!")
        sys.exit(0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            msg_id = req.get("id")
            method = req.get("method")
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "LongHorizonAutonomousTaskResumptionEngine", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "manage_long_horizon_resumption",
                            "description": "Manage persistent multi-day autonomous agent execution: create resumable sessions, record idempotent state events, suspend for user inputs, and restore execution safely.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "enum": ["create_task_session", "record_step_checkpoint", "suspend_for_approval", "resume_task_session", "get_session_state"]},
                                    "session_id": {"type": "string"},
                                    "task_goal": {"type": "string"},
                                    "idempotency_key": {"type": "string"},
                                    "step_name": {"type": "string"},
                                    "step_payload": {"type": "object"},
                                    "approval_prompt": {"type": "string"},
                                    "resume_token": {"type": "string"}
                                },
                                "required": ["action"]
                            }
                        }]
                    }
                }
            elif method == "tools/call":
                res = handle_call_tool(req.get("params", {}))
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
                }
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            print(json.dumps(resp), flush=True)
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            print(json.dumps(err_resp), flush=True)

if __name__ == "__main__":
    main()
