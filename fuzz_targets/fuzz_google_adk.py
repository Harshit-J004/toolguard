"""
Proof of Concept: Fuzzing Google Agent Development Kit (ADK)
"""

from toolguard import test_chain
from toolguard.integrations.google_adk import guard_google_adk_tool

# 1. Simulate the underlying Python function
def generate_sql(table: str, limit: int = 10) -> str:
    """Generates a SQL query for the given table."""
    return f"SELECT * FROM {table} LIMIT {limit};"

# 2. Simulate the Google ADK FunctionTool object
class MockGoogleADKTool:
    def __init__(self, func):
        self.name = func.__name__
        self.description = func.__doc__
        self.func = func  # Google ADK uses .func (or ._func)

# 3. Create the simulated tool
adk_tool = MockGoogleADKTool(generate_sql)

# 4. Wrap it using ToolGuard's adapter
guarded = guard_google_adk_tool(adk_tool)

if __name__ == "__main__":
    print(f"\n🚀 Fuzzing Google ADK Tool: {guarded.name}")
    print("-" * 50)
    
    # 5. Run the fuzzer to prove it catches bad LLM payloads
    report = test_chain(
        [guarded], 
        test_cases=["null_handling", "type_mismatch", "prompt_injection"],
        iterations=1,
        assert_reliability=0.0
    )
    
    from toolguard.reporters.console import print_chain_report
    print_chain_report(report)
