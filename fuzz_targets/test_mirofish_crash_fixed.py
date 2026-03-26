import time
from toolguard.integrations.openai_func import from_openai_function
from toolguard.core.chain import test_chain
import io, contextlib

def db_transfer(user_id: str, amount: int) -> str:
    return f"Transferred {amount} to {user_id.upper()}"

# MiroFish uses ZepTools which uses OpenAI native JSON schemas
openai_schema = {
    "name": "db_transfer",
    "description": "Transfer money",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "amount": {"type": "integer"}
        },
        "required": ["user_id", "amount"]
    }
}

guarded_tool = from_openai_function(openai_schema, db_transfer)

print("🧪 Testing Framework 3: MiroFish (OpenAI Native Schema)")
start = time.time()

with contextlib.redirect_stdout(io.StringIO()):
    report = test_chain([guarded_tool], base_input={"user_id": "usr_123", "amount": 100}, assert_reliability=0.0)

crashes = len([s for r in report.runs for s in r.steps if not s.success])
elapsed = time.time() - start

print(f"Result:")
print(f"↳ Injected {len(report.runs)} LLM Hallucinations.")
print(f"↳ Intercepted {crashes} Unhandled Python Crashes.")
print(f"↳ Time elapsed: {elapsed:.2f} seconds")
