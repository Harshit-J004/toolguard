import time
from toolguard.core.chain import test_chain
from toolguard.integrations.swarm import guard_swarm_agent
from swarm import Agent
import io, contextlib

# 1. Fragile target tool
def db_transfer(user_id: str, amount: int) -> str:
    # Throws AttributeError if user_id is None
    return f"Transferred {amount} to {user_id.upper()}"

# 2. Wrap it natively in Swarm
swarm_agent = Agent(name="FinanceBot", functions=[db_transfer])
guarded_swarm = guard_swarm_agent(swarm_agent)

print("🧪 Testing Framework 2: OpenAI Swarm")
start = time.time()

# 3. Suppress output and natively fuzz the integration
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded_swarm.functions[0]], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
