import sys
import os

# Add ToolGuard to path
sys.path.insert(0, os.path.abspath("."))

from autogen_core.tools import FunctionTool
from toolguard.integrations.autogen import guard_autogen_tool
from toolguard.core.tracer import TraceTracker

# 1. Define real tools
def authenticate_user(user_id: int) -> dict:
    """Authenticates the user into the system."""
    print(f"Executing: authenticate_user(user_id={user_id})")
    return {"status": "success", "session_id": "sess_123"}

def process_refund(session_id: str, amount: float) -> dict:
    """Processes a refund for the authenticated session."""
    print(f"Executing: process_refund(session_id={session_id}, amount={amount})")
    return {"status": "refund_issued", "transaction_id": "tx_999"}

# 2. Wrap them as AutoGen tools
ag_auth = FunctionTool(authenticate_user, name="auth", description="User authentication")
ag_refund = FunctionTool(process_refund, name="refund", description="Refund processing")

# 3. Apply ToolGuard protection (this is what devs do in production)
guarded_auth = guard_autogen_tool(ag_auth)
guarded_refund = guard_autogen_tool(ag_refund)

print("\n--- STARTING GOLDEN TRACE TEST (AUTOGEN) ---")

# 4. Use TraceTracker to capture the "Golden Path"
try:
    with TraceTracker() as trace:
        # Simulate an Agentic Orchestration sequence: [auth, refund]
        print("\n[Orchestrator] Step 1: Authenticating...")
        guarded_auth(user_id=42)
        
        print("[Orchestrator] Step 2: Processing Refund...")
        guarded_refund(session_id="sess_123", amount=50.0)

        # 5. Assert the sequence
        print("\n[ToolGuard] Asserting mandatory sequence: ['auth', 'refund']...")
        trace.assert_sequence(["auth", "refund"])
        print("✅ Sequence Assertion Passed!")

        print("\n[ToolGuard] Asserting EXACT golden path: ['auth', 'refund']...")
        trace.assert_golden_path(["auth", "refund"])
        print("✅ Golden Path Assertion Passed!")

        # 6. Test a failing assertion (out of order/missing)
        print("\n[ToolGuard] Testing invalid sequence assertion (should fail)...")
        try:
            trace.assert_sequence(["refund", "auth"])
        except Exception as e:
            print(f"✅ Correctly caught mismatch: {e}")

except Exception as e:
    print(f"❌ unexpected test failure: {e}")
    sys.exit(1)

print("\n--- TEST COMPLETE: Golden Traces are working perfectly on AutoGen! ---")
