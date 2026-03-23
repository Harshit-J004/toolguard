import sys
import os
import asyncio
from typing import Any

# Add ToolGuard to path
sys.path.insert(0, os.path.abspath("."))

from toolguard.core.validator import create_tool
from toolguard.core.errors import ToolGuardApprovalDeniedError

# 1. Mock a MiroFish-style Service (similar to ZepToolsService)
class MockMiroFishZepService:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.config = {"memory_type": "perpetual"}

    async def clear_knowledge_graph(self, reason: str) -> str:
        """DESTRUCTIVE: Resets the entire agentic memory graph for this session."""
        print(f"CRITICAL: Clearing Knowledge Graph for agent {self.agent_id}. Reason: {reason}")
        return f"Knowledge Graph for {self.agent_id} has been completely wiped."

# 2. Instantiate the service
mirofish_service = MockMiroFishZepService(agent_id="report_agent_001")

# 3. Secure the destructive method with ToolGuard Risk Tier 2
# (In a real MiroFish app, u'd wrap their Zep client calls)
guarded_clear_graph = create_tool(risk_tier=2)(mirofish_service.clear_knowledge_graph)

async def run_test():
    print("\n--- STARTING MIROFISH RISK TIER VERIFICATION ---")

    # TEST A: Headless / Non-Interactive Safety (Auto-Deny)
    print("\n[Test A] Attempting Tier 2 execution in headless mode (should auto-deny)...")
    try:
        # ToolGuard will trigger the Approval Prompt, but since there is no TTY,
        # it will catch EOFError and auto-deny, raising ToolGuardApprovalDeniedError.
        await guarded_clear_graph(reason="Routine database maintenance")
        print("❌ FAILURE: MiroFish graph cleared without approval!")
    except ToolGuardApprovalDeniedError as e:
        print(f"✅ SUCCESS: Intercepted dangerous MiroFish action. Error: {e}")

    # TEST B: CI/CD Bypass (Auto-Approve)
    print("\n[Test B] Attempting Tier 2 execution with TOOLGUARD_AUTO_APPROVE=1...")
    os.environ["TOOLGUARD_AUTO_APPROVE"] = "1"
    try:
        result = await guarded_clear_graph(reason="Automated pipeline cleanup")
        print(f"✅ SUCCESS: Action approved via environment variable. Result: {result}")
    except Exception as e:
        print(f"❌ FAILURE: Action was blocked even with AUTO_APPROVE. Error: {e}")
    finally:
        del os.environ["TOOLGUARD_AUTO_APPROVE"]

if __name__ == "__main__":
    asyncio.run(run_test())
    print("\n--- TEST COMPLETE: MiroFish Risk Tiers are fully operational! ---")
