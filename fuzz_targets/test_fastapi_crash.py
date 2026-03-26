import time
from toolguard.core.chain import test_chain
from toolguard.integrations.fastapi import as_fastapi_tool
import io, contextlib

# 1. A fragile native Python backend tool
def db_transfer(user_id: str, amount: int) -> str:
    # This will throw an AttributeError if LLM passes None
    return f"Transferred {amount} to {user_id.upper()}"

# 2. Wrap it for FastAPI
guarded_fastapi = as_fastapi_tool(db_transfer)

print("🧪 Testing Framework 1: FastAPI / Native Python")
start = time.time()

# 3. Suppress emojis and run the fuzzer to simulate LLM hallucinations
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded_fastapi], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

# 4. Count the fatal crashes intercepted
crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
