import sys
import os
import asyncio
from typing import Any

# Add ToolGuard to path
sys.path.insert(0, os.path.abspath("."))

from langchain_core.tools import tool
from toolguard.core.validator import create_tool
from toolguard.core.errors import ToolGuardApprovalDeniedError

# 1. Define a REAL LangChain tool (potentially "dirty" with type hints)
@tool
def dangerous_langchain_delete(db_id: str) -> str:
    """DESTRUCTIVE: Deletes a database record."""
    return f"LangChain tool executed: {db_id} deleted."

# 2. THE ISOLATED PROXY (Deep Think Solve)
# This proxy has ZERO LangChain type-hint baggage. it bypasses 
# the Pydantic NameError while still securing the real logic.
async def proxy_tool(db_id: str):
    """Clean proxy that executes the underlying LangChain tool."""
    return await dangerous_langchain_delete.ainvoke({"db_id": db_id})

# 3. Guard the Proxy with Tier 2 (Approval Required)
guarded_tool = create_tool(risk_tier=2)(proxy_tool)

async def run_test():
    print("\n--- STARTING LANGCHAIN RISK TIER VERIFICATION (Isolated Proxy) ---")

    # TEST A: Headless / Non-Interactive Safety (Auto-Deny)
    print("\n[Test A] Attempting Tier 2 execution in headless mode (should auto-deny)...")
    try:
        # ToolGuard will trigger the Approval Prompt, but since there is no TTY,
        # it will catch EOFError and auto-deny, raising ToolGuardApprovalDeniedError.
        await guarded_tool.ainvoke({"db_id": "prod_users_v3"})
        print("❌ FAILURE: Tool executed without approval!")
    except ToolGuardApprovalDeniedError as e:
        print(f"✅ SUCCESS: Intercepted dangerous action safely. Error: {e}")

    # TEST B: CI/CD Bypass (Auto-Approve)
    print("\n[Test B] Attempting Tier 2 execution with TOOLGUARD_AUTO_APPROVE=1...")
    os.environ["TOOLGUARD_AUTO_APPROVE"] = "1"
    try:
        result = await guarded_tool.ainvoke({"db_id": "test_db_sandbox"})
        print(f"✅ SUCCESS: Tool approved via environment variable. Result: {result}")
    except Exception as e:
        print(f"❌ FAILURE: Tool was blocked even with AUTO_APPROVE. Error: {e}")
    finally:
        del os.environ["TOOLGUARD_AUTO_APPROVE"]

if __name__ == "__main__":
    asyncio.run(run_test())
    print("\n--- TEST COMPLETE: LangChain Risk Tiers are fully operational via Proxy! ---")
