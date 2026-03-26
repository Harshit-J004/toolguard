import time
from swarm import Agent
from toolguard.integrations.swarm import guard_swarm_agent
from toolguard.core.chain import test_chain
import io, contextlib

def db_transfer(user_id: str, amount: int) -> str:
    # Vanilla Python backend tool
    return f"Transferred {amount} to {user_id.upper()}"

# Initialize Swarm Agent properly
agent = Agent(name="FinanceBot", functions=[db_transfer])
# Guard it
guarded_agent = guard_swarm_agent(agent)

print("🧪 Testing Framework 2: OpenAI Swarm")
start = time.time()

# Pass the entire agent to test_chain so it resolves contexts natively
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain(guarded_agent, base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
