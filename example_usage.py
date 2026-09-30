"""Example usage for LongHorizonAutonomousTaskResumptionEngine."""
import json
from client import LongHorizonAutonomousTaskResumptionEngine

def main():
    print("=== Long-Horizon Autonomous Task Checkpoint & Resumption Demo ===")
    engine = LongHorizonAutonomousTaskResumptionEngine()

    # 1. Start multi-day task session (Meta Muse background shopping / travel agent)
    print("\n--- 1. Creating Long-Horizon Persistent Session ---")
    session = engine.create_task_session(
        task_goal="Monitor Black Friday deals for Sony WH-1000XM5 and auto-checkout if under $280",
        initial_context={"target_sku": "SONY-XM5", "target_price": 280.0},
        idempotency_key="TASK-GOAL-SONY-2026"
    )
    sid = session["session_id"]
    print(f"Session ID: {sid}, Status: {session['status']}")

    # 2. Checkpoints across days
    print("\n--- 2. Recording Intermediate Autonomous Execution Checkpoints ---")
    engine.record_step_checkpoint(sid, "DAY_1_PRICE_POLL", {"price_seen": 349.99})
    engine.record_step_checkpoint(sid, "DAY_2_PRICE_DROP", {"price_seen": 274.50, "context_delta": {"matched_merchant": "BestBuy"}})

    # 3. Pause for user final payment confirmation
    print("\n--- 3. Suspending Execution for User Approval Gate ---")
    sus = engine.suspend_for_approval(
        session_id=sid,
        approval_prompt="Deal found at BestBuy for $274.50 (Save $75). Confirm authorization to charge stored card ending in 4242?",
        pending_action_payload={"charge_amount": 274.50, "merchant": "BestBuy"}
    )
    print(f"Suspended! Prompt: '{sus['approval_prompt']}'")
    print(f"Resume Token Generated: {sus['resume_token']}")

    # 4. User taps 'Approve' in WhatsApp / Messenger / WorkBuddy
    print("\n--- 4. Resuming Task Execution Post-Approval ---")
    resumed = engine.resume_task_session(sid, sus["resume_token"], user_decision="APPROVED")
    print(json.dumps(resumed, indent=2))

    # 5. Inspect final session state
    final_state = engine.get_session_state(sid)
    print(f"\nTotal Steps Recorded: {len(final_state['checkpoints'])}, Final Status: {final_state['status']}")

if __name__ == "__main__":
    main()
