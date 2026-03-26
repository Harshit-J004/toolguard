"""
Proof of Concept: Fuzzing OpenAI Agents SDK
"""

from toolguard import test_chain
from toolguard.integrations.openai_agents import guard_openai_agents_tool

# 1. Simulate the underlying Python function
def book_flight(destination: str, passengers: int) -> dict:
    """Books a flight for the user."""
    return {"status": "success", "dest": destination, "count": passengers}

# 2. Simulate the OpenAI Agents SDK @function_tool object
class MockOpenAIAgentsTool:
    def __init__(self, func):
        self.name = func.__name__
        self.description = func.__doc__
        self.fn = func  # OpenAI Agents SDK uses .fn (or ._func)

# 3. Create the simulated tool
agents_tool = MockOpenAIAgentsTool(book_flight)

# 4. Wrap it using ToolGuard's adapter
guarded = guard_openai_agents_tool(agents_tool)

if __name__ == "__main__":
    print(f"\n🚀 Fuzzing OpenAI Agents SDK Tool: {guarded.name}")
    print("-" * 50)
    
    # 5. Run the fuzzer to prove it catches bad LLM payloads
    report = test_chain(
        [guarded], 
        test_cases=["null_handling", "type_mismatch", "missing_fields"],
        iterations=1,
        assert_reliability=0.0
    )
    
    from toolguard.reporters.console import print_chain_report
    print_chain_report(report)
