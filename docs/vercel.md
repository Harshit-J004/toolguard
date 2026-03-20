# Vercel AI SDK Integration

When using the [Vercel AI SDK](https://sdk.vercel.ai/docs) in your React/Next.js frontend, you are likely exposing a Python FastAPI/Flask backend to handle the actual server-side tool execution via the `core/tools` APIs.

If the LLM running on the Vercel edge hallucinates a malformed JSON payload, your Python backend needs to be resilient enough to handle it without crashing the API process.

## Testing Backend APIs with ToolGuard

You can natively test your backend functions using the FastAPI integration layer.

### Example Setup

```python
from fastapi import FastAPI
from toolguard.integrations.fastapi import as_fastapi_tool
from toolguard.core.chain import test_chain

app = FastAPI()

# 1. The core logic powering your Vercel frontend tool
def fetch_user_data(user_id: int) -> dict:
    """Fetch user intelligence from DB."""
    return {"id": user_id, "name": "Alice"}

# 2. The endpoint mapped to the Vercel AI SDK
@app.post("/api/tools/fetch_user")
async def api_fetch_user(user_id: int):
    return fetch_user_data(user_id)

# 3. Running Pre-Flight Reliability Tests
if __name__ == "__main__":
    # Simulate Vercel AI SDK sending hallucinated/malformed payloads
    # directly against your backend logic.
    report = test_chain(
        [as_fastapi_tool(fetch_user_data)],
        assert_reliability=0.90
    )
    print(report.summary())
```

Testing the `fetch_user_data` function deterministically guarantees that if the Vercel `useChat` hook sends a string instead of an integer `user_id`, your backend will gracefully handle the validation error instead of throwing a 500 Server Crash.
