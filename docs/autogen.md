# Microsoft AutoGen Integration

ToolGuard natively integrates with [Microsoft AutoGen](https://microsoft.github.io/autogen/) `FunctionTool` objects.

## Zero-Config Testing
ToolGuard CLI automatically detects instances of `autogen_core.tools.FunctionTool` in your scripts:
```bash
toolguard run my_autogen_agent.py
```

## Programmatic Usage
```python
from autogen_core.tools import FunctionTool
from toolguard.integrations.autogen import guard_autogen_tool
from toolguard.core.chain import test_chain

def fetch_data(key: str) -> str:
    return "Data"

autogen_tool = FunctionTool(fetch_data, name="fetch_data", description="Fetches data")

# Wrap it for Fuzzing!
guarded = guard_autogen_tool(autogen_tool)

if __name__ == "__main__":
    test_chain([guarded], assert_reliability=0.95)
```
