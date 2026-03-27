# LangChain Integration

ToolGuard natively integrates with [LangChain](https://www.langchain.com/) `BaseTool` instances — including tools created with the `@tool` decorator.

## Zero-Config Testing
ToolGuard CLI automatically detects LangChain tools in your scripts:
```bash
toolguard run my_langchain_agent.py
```

## Programmatic Usage
```python
from langchain_core.tools import tool
from toolguard.integrations.langchain import guard_langchain_tool
from toolguard.core.chain import test_chain

@tool
def search(query: str) -> str:
    """Search the web for information."""
    return "Results..."

# Wrap a single tool
guarded = guard_langchain_tool(search)

if __name__ == "__main__":
    report = test_chain([guarded], assert_reliability=0.95)
    print(report.summary())
```

## Batch Conversion
Convert an entire list of LangChain tools at once:
```python
from toolguard.integrations.langchain import langchain_tools_to_chain

tools = [search, calculator, retriever]
guarded_chain = langchain_tools_to_chain(tools)
report = test_chain(guarded_chain, assert_reliability=0.95)
```

## How It Works

ToolGuard extracts the underlying Python function from your LangChain tool by checking for:

1. `.func` attribute (from `@tool` decorated functions)
2. `.coroutine` attribute (async tools)
3. `._run()` method (from `BaseTool` subclasses)
4. `.invoke()` fallback

The extracted function is wrapped in a `GuardedTool` with the original tool's `name` and `description` preserved.
