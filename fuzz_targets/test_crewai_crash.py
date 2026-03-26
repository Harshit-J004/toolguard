import time
from toolguard.core.chain import test_chain
from toolguard.integrations.crewai import guard_crewai_tool
from crewai.tools import tool as crew_tool
import io, contextlib

@crew_tool("db_transfer")
def db_transfer(user_id: str, amount: int) -> str:
    """Transfer Money."""
    return f"Transferred {amount} to {user_id.upper()}"

guarded = guard_crewai_tool(db_transfer)

print("🧪 Testing Framework 4: CrewAI")
start = time.time()
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
