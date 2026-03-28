import asyncio
from toolguard.integrations.langchain import guard_langchain_tool
from toolguard.alerts.config import configure_alerts
import toolguard.alerts.manager as alerts_manager
from toolguard.core.report import ChainTestReport, ChainRun

# 1. Mock LangChain Async Tool
class MockBaseTool:
    """Mock simulating langchain_core.tools.BaseTool to bypass the type check."""
    @classmethod
    def __instancecheck__(cls, instance):
        return True # Mock isinstance check

class MockLCTool(MockBaseTool):
    name = "mock_async_fetch"
    description = "Mock tool"
    
    def func(self, x: str):
        return "SYNC_" + x
        
    async def coroutine(self, x: str):
        return "ASYNC_" + x

import sys

def test_async_extraction():
    print("[TEST 1] Testing Async LangChain/CrewAI .coroutine extraction")
    mock_tool = MockLCTool()
    
    # ToolGuard dynamically imports langchain_core.tools.BaseTool INSIDE the function.
    # We must spoof sys.modules to intercept it.
    class DummyModule:
        BaseTool = MockBaseTool
        
    sys.modules["langchain_core"] = DummyModule()
    sys.modules["langchain_core.tools"] = DummyModule()
    
    try:
        guarded = guard_langchain_tool(mock_tool)
        
        # DEBUG: Let's see what was extracted
        print(f"DEBUG: extracted func: {getattr(guarded, '_func', None)}")
        print(f"DEBUG: _is_async flag: {getattr(guarded, '_is_async', False)}")
        
        is_async = asyncio.iscoroutinefunction(guarded) or getattr(guarded, "_is_async", False)
        if not is_async:
            raise AssertionError("FAIL: guard_langchain_tool failed to extract the async .coroutine!")
    finally:
        del sys.modules["langchain_core"]
        del sys.modules["langchain_core.tools"]
        
    print("✅ PASS: Successfully extracted .coroutine over sync .func for async frameworks")

def test_strip_traceback():
    print("\n[TEST 2] Testing Webhook strip_traceback=True safety")
    configure_alerts(slack_webhook_url="http://mock", strip_traceback=True)
    
    # Mock the safe_call sender so we can inspect the payload without HTTP
    captured = []
    def mock_safe_call(func, url, alert_data):
        captured.append(alert_data)
        
    alerts_manager._WORKER_POOL.submit = lambda func, *args: mock_safe_call(args[0], args[1], args[2])
    
    try:
        1 / 0
    except Exception as e:
        alerts_manager.dispatch_alert("test_tool", {"a": 1}, e)
        
        payload = captured[0] if captured else {}
        traceback_val = payload.get("traceback", "")
        
        if "ZeroDivisionError" in traceback_val or "line" in traceback_val:
             raise AssertionError("FAIL: Raw traceback leaked into payload despite strip_traceback=True!")
        
        if "STRIPPED" not in traceback_val:
             raise AssertionError("FAIL: No STRIPPED notice found in payload!")
             
        print("✅ PASS: Raw tracebacks successfully stripped from outgoing webhooks")

def test_coverage_overflow():
    print("\n[TEST 3] Testing Coverage Percentile Overflow Safety")
    
    # Simulate a run that covered 15 different categories (some real, some hallucinated/custom)
    runs = []
    crazy_categories = ["happy_path", "null_handling", "extra_fields", "prompt_injection", "alien_attack", "buffer_overflow", "quantum_injection"]
    
    for cat in crazy_categories:    
        runs.append(ChainRun(success=True, test_case_type=cat))
        
    report = ChainTestReport(chain_name="Overflow Check", runs=runs, tool_names=["mock"])
    
    # Coverage should be bound strictly to 1.0 (or a fraction) relative to the 9 absolute core categories.
    if report.coverage_percent > 1.0:
        raise AssertionError(f"FAIL: Coverage overflowed to {report.coverage_percent}!")
        
    print(f"✅ PASS: Coverage bounded safely to {report.coverage_percent:.2f} ({(report.coverage_percent*100):.0f}%) despite {len(crazy_categories)} overlapping test cases")

if __name__ == "__main__":
    print("🚀 Running Ecosystem Patches Verifications...\n")
    test_async_extraction()
    test_strip_traceback()
    test_coverage_overflow()
    print("\n🎉 All 3 Ecosystem Patches rigorously verified!")
