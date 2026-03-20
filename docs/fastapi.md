# FastAPI Backend Integration

When building production AI systems, LLM tools are frequently executed as backend webhooks or API routes (especially when using frontends like Vercel AI SDK).

ToolGuard natively supports fuzzing your [FastAPI](https://fastapi.tiangolo.com/) route handlers. This ensures your server won't throw unhandled `HTTP 500` errors if an LLM hallucinates a bad JSON payload.

## Programmatic Usage
Simply wrap your FastAPI endpoint or backend function with `as_fastapi_tool`.

```python
from fastapi import FastAPI
from toolguard.integrations.fastapi import as_fastapi_tool
from toolguard.core.chain import test_chain

app = FastAPI()

def fetch_user_data(user_id: int) -> dict:
    """Fetch user intelligence from DB."""
    return {"id": user_id, "name": "Alice"}


@app.post("/api/tools/fetch_user")
async def api_fetch_user(user_id: int):
    return fetch_user_data(user_id)


if __name__ == "__main__":
    # Test your backend function against malicious/hallucinated payloads
    report = test_chain([as_fastapi_tool(fetch_user_data)])
    print(report.summary())
```
