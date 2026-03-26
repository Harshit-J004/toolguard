import time
from toolguard.core.chain import test_chain
from toolguard.integrations.langchain import guard_langchain_tool
from langchain_core.tools import tool as lc_tool
import io, contextlib

# 1. Fragile Target Tool wrapped in LangChain Core
@lc_tool
def db_transfer(user_id: str, amount: int) -> str:
    """Transfer Money."""
    # Throws AttributeError if user_id is None
    return f"Transferred {amount} to {user_id.upper()}"

# 2. Guard it
guarded_lc = guard_langchain_tool(db_transfer)

print("🧪 Testing Framework 3: LangChain")
start = time.time()

# 3. Suppress output and natively fuzz the integration
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded_lc], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
