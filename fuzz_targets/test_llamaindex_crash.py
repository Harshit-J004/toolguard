import time
from toolguard.core.chain import test_chain
from toolguard.integrations.llamaindex import guard_llamaindex_tool
from llama_index.core.tools import FunctionTool
import io, contextlib

def db_transfer(user_id: str, amount: int) -> str:
    return f"Transferred {amount} to {user_id.upper()}"

llama_t = FunctionTool.from_defaults(fn=db_transfer)
guarded = guard_llamaindex_tool(llama_t)

print("🧪 Testing Framework 5: LlamaIndex")
start = time.time()
with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
