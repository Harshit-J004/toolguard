import sys
import os
from typing import Any

# Add ToolGuard to path
sys.path.insert(0, os.path.abspath("."))

from autogen_core.tools import FunctionTool
from toolguard.integrations.autogen import guard_autogen_tool
from toolguard.core.chain import test_chain

# 1. Custom class to test "Recursive Depth-First Memory Parsing"
class SafeDocument:
    def __init__(self, title: str, body: str):
        self.metadata = {"confidential": False, "category": "public"}
        self.body = body  # <--- The malicious jailbreak will be hidden here...
    
    def __repr__(self):
        return f"<SafeDocument '{self.body[:20]}...'>"

# 2. Define a vulnerable tool for AutoGen
def fetch_user_data(query: str) -> Any:
    """Fetches user documentation based on a search query."""
    print(f"Executing: fetch_user_data(query='{query[:50]}...')")
    # Simulate a database reflection (vulnerable pattern)
    return SafeDocument(title="Search Result", body=query)

# 3. Apply ToolGuard protection
ag_tool = FunctionTool(fetch_user_data, name="search_docs", description="Searches docs")
guarded_tool = guard_autogen_tool(ag_tool)

print("\n--- STARTING AUTOGEN RECURSIVE INJECTION TEST ---")

try:
    # 4. Run the fuzzer specifically for prompt_injection
    # ToolGuard will inject '[SYSTEM OVERRIDE]...' into the query string
    report = test_chain(
        [guarded_tool],
        base_input={"query": "Find me the HR handbook"},
        test_cases=["prompt_injection"],
        iterations=1,
        assert_reliability=0.0 # Don't crash the script on failure
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
                print("    nested SafeDocument.body attribute, but the Recursive DFS Scanner")
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

print("\n--- TEST COMPLETE: Recursive Injection Defense Verified on AutoGen! ---")
