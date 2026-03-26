import sys
import os
from typing import Any

# Add ToolGuard to path
sys.path.insert(0, os.path.abspath("."))

# MONKEY-PATCH LangChain internal namespace to fix the ToolCall NameError.
# This is required because Pydantic's get_type_hints() resolves forward refs 
# in the module where they were defined, and LangChain 0.3.x sometimes fails 
# this when another library (ToolGuard) introspects them.
import langchain_core.tools
try:
    from langchain_core.messages import ToolCall
    # Inject ToolCall directly into the langchain_core.tools namespace
    langchain_core.tools.ToolCall = ToolCall
except ImportError:
    pass

from langchain_core.tools import tool
from toolguard.integrations.langchain import guard_langchain_tool
from toolguard.core.chain import test_chain

# A Custom class to test "Recursive Depth-First Memory Parsing"
# ToolGuard claims it can find payloads hidden inside __dict__ of custom classes
class DatabaseRecord:
    def __init__(self, raw_data: str):
        self.metadata = {"source": "fuzz_database", "version": 1.0}
        self.raw_content = raw_data  # <--- The payload will be hidden here
    
    def __repr__(self):
        return f"<DatabaseRecord content_len={len(self.raw_content)}>"

@tool
def vulnerable_search(query: str) -> str:
    """Searches the database for a query and returns a complex object."""
    print(f"Executing: vulnerable_search(query='{query[:50]}...')")
    # We return the object, which is "malformed" according to the "str" hint,
    # but that's what a real vulnerable tool would do to bypass simple checks.
    return DatabaseRecord(raw_data=query)

# Wrap it with ToolGuard (using the REAL LangChain integration)
guarded_tool = guard_langchain_tool(vulnerable_search)

print("\n--- STARTING LANGCHAIN RECURSIVE INJECTION TEST (Monkey-Patched) ---")

try:
    # Run the fuzzer specifically for prompt_injection
    # This will inject '[SYSTEM OVERRIDE]...' into the query
    report = test_chain(
        [guarded_tool],
        base_input={"query": "Find recent user reviews"},
        test_cases=["prompt_injection"],
        iterations=1,
        assert_reliability=0.0 # Don't crash the script on failure, we WANT to report it
    )

    print("\n" + "="*50)
    print("                AUDIT RESULTS                ")
    print("="*50)
    
    found_vuln = False
    for run in report.runs:
        for step in run.steps:
            if step.error_type == "PromptInjectionVulnerability":
                print(f"\n[🚨] VULNERABILITY DETECTED: {step.error_type}")
                print(f"    Tool: {step.tool_name}")
                print(f"    Message: {step.error}")
                print("\n[🛡️] TOOLGUARD SUCCESS: The malicious payload was hidden inside a")
                print("    nested DatabaseRecord.__dict__, but the Recursive DFS Scanner")
                print("    successfully intercepted and blocked it!")
                found_vuln = True

    if not found_vuln:
        print("\n❌ Unexpected Result: ToolGuard missed the injection!")
        sys.exit(1)

except Exception as e:
    import traceback
    print("\n❌ Test crashed during execution:")
    traceback.print_exc()
    sys.exit(1)

print("\n--- TEST COMPLETE: Recursive Injection Defense Verified on LangChain! ---")
