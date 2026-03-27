# Google Agent Development Kit (ADK) Integration

ToolGuard natively integrates with the [Google Agent Development Kit](https://google.github.io/adk-docs/) `FunctionTool` objects.

## Zero-Config Testing
ToolGuard CLI automatically detects Google ADK tools in your scripts:
```bash
toolguard run my_adk_agent.py
```

## Programmatic Usage
```python
from google.adk.tools import FunctionTool
from toolguard.integrations.google_adk import guard_google_adk_tool
from toolguard.core.chain import test_chain

def fetch_stock_price(ticker: str) -> float:
    """Fetch the current stock price."""
    return 150.25

adk_tool = FunctionTool(func=fetch_stock_price)

# Wrap it for fuzzing
guarded = guard_google_adk_tool(adk_tool)

if __name__ == "__main__":
    report = test_chain([guarded], assert_reliability=0.95)
    print(report.summary())
```

## How It Works

ToolGuard extracts the underlying Python function via the `.func` or `._func` attribute on the Google ADK `FunctionTool` object. The tool's `name` and `description` metadata are automatically preserved.
