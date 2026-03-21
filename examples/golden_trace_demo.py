from toolguard import create_tool, TraceTracker, ToolGuardTraceMismatchError

@create_tool()
def read_memory() -> str:
    return "User is VIP"

@create_tool()
def search_database() -> str:
    return "Product found"

@create_tool()
def issue_refund() -> str:
    return "Refunded"

# Simulate an LLM agent execution loop (e.g. LangChain AgentExecutor)
# The prompt instructed the LLM: "You MUST read memory, search DB, then refund"
def run_rogue_agent_loop():
    print("Agent decides to skip reading memory and searching the database!")
    print("Agent immediately issues the refund!")
    issue_refund()

print("\n🚀 Starting Production LLM Agent Simulation...")

try:
    with TraceTracker() as trace:
        # 1. Run the agent (could be LangChain, CrewAI, AutoGen, etc.)
        run_rogue_agent_loop()
        
        # 2. Assert the expected mathematical execution graph
        trace.assert_golden_path(["read_memory", "search_database", "issue_refund"])

except ToolGuardTraceMismatchError as e:
    print(f"\n[SYSTEM GUARD CAUGHT ERROR] {type(e).__name__} - {e}")
    print("Agent execution blocked because it deviated from the Golden Trace!")
