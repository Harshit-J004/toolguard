import sys
import os
from toolguard import create_tool
from toolguard.core.errors import ToolGuardApprovalDeniedError

# Disable auto-approve for the demo so we force interactive prompts
if "TOOLGUARD_AUTO_APPROVE" in os.environ:
    del os.environ["TOOLGUARD_AUTO_APPROVE"]

@create_tool(risk_tier=2)
def refund_customer_order(order_id: str, amount: float) -> str:
    # This line of code will mathematically NEVER EXECUTE unless the human hits 'y'
    print("\n[KERNEL] => PHYSICAL PYTHON FUNCTION EXECUTING!")
    print(f"[KERNEL] => Processing real refund logic for: {amount}...")
    return f"Successfully refunded ${amount} for order {order_id}"

print("\n🚀 Starting Native Execution Test...")

try:
    print("[SYSTEM] Attempting to call refund_customer_order()...")
    result = refund_customer_order(order_id="ORD-123", amount=5000.0)
    print(f"[SYSTEM] Call finished successfully. Returned data: {result}")
except ToolGuardApprovalDeniedError as e:
    print(f"\n[SYSTEM GUARD CAUGHT ERROR] {type(e).__name__} - {e}")
    print("[SYSTEM] Notice that the [KERNEL] logs NEVER printed! The wrapper killed it physically!")
except Exception as e:
    print(f"\n[UNKNOWN CAUGHT ERROR] {type(e).__name__} - {e}")
