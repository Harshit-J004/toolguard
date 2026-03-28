import sys
import asyncio
from toolguard.integrations.crewai import guard_crewai_tool

class DummyCrewModule:
    class BaseTool:
        pass

# Spoof sys.modules to pass the "is crewai installed" check safely
sys.modules["crewai"] = DummyCrewModule()
sys.modules["crewai.tools"] = DummyCrewModule()

# MOCK CREWAI TOOLS
class ShadowedCrewTool:
    name = "shadowed_tool"
    description = "A deeply shadowed tool"
    
    def func(self):
        return "SYNC_FUNC"
        
    def _run(self):
        return "SYNC_RUN"
        
    async def _arun(self):
        return "ASYNC_ARUN"

class SyncOnlyCrewTool:
    name = "legacy_sync"
    description = "Only has _run"
    
    def _run(self):
        return "LEGACY_RUN"

def test_shadowed_extraction():
    print("\n[TEST 1] Testing Async _arun Priority over .func and ._run")
    tool = ShadowedCrewTool()
    
    guarded = guard_crewai_tool(tool)
    
    # ToolGuard extracts the underlying function. The wrapper tracks _is_async natively!
    is_async = getattr(guarded, "_is_async", False)
    func_name = getattr(guarded._func, "__name__", "")
    
    if not is_async:
        raise AssertionError("FAIL: guard_crewai_tool fell back to a synchronous endpoint instead of _arun!")
        
    if func_name != "_arun":
        raise AssertionError(f"FAIL: Extracted wrong endpoint! Expected '_arun', got '{func_name}'")
        
    print(f"✅ PASS: CrewAI accurately prioritized async '{func_name}' over sync shadows!")

def test_sync_fallback():
    print("\n[TEST 2] Testing Legacy ._run Fallback Extraction")
    tool = SyncOnlyCrewTool()
    
    guarded = guard_crewai_tool(tool)
    
    is_async = getattr(guarded, "_is_async", False)
    func_name = getattr(guarded._func, "__name__", "")
    
    if is_async:
        raise AssertionError("FAIL: Wrapper falsely identified a synchronous function as async!")
        
    if func_name != "_run":
         raise AssertionError(f"FAIL: Expected '_run', got '{func_name}'")
         
    print(f"✅ PASS: Successfully extracted legacy synchronous fallback: '{func_name}'")
    
def test_metadata_binding():
    print("\n[TEST 3] Testing CrewAI Metadata Proxy Binding")
    tool = ShadowedCrewTool()
    guarded = guard_crewai_tool(tool)
    
    if guarded.name != "shadowed_tool":
        raise AssertionError(f"FAIL: Name bound incorrectly: {guarded.name}")
        
    if guarded.description != "A deeply shadowed tool":
        raise AssertionError(f"FAIL: Description bound incorrectly: {guarded.description}")
        
    print("✅ PASS: CrewAI Swarm Identity tags perfectly mapped to the GuardedTool proxy.")

if __name__ == "__main__":
    print("🚀 Running Dedicated CrewAI Async Priority Audit...\n")
    try:
        test_shadowed_extraction()
        test_sync_fallback()
        test_metadata_binding()
        print("\n🎉 ALL 3 CREWAI ORCHESTRATOR TESTS RIGOROUSLY VERIFIED!")
    finally:
        del sys.modules["crewai"]
        del sys.modules["crewai.tools"]
