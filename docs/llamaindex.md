# LlamaIndex Integration

ToolGuard provides native, zero-config support for testing tools built with [LlamaIndex](https://www.llamaindex.ai/).

Enterprise RAG pipelines often rely on `FunctionTool` or `AsyncFunctionTool`. If the LLM router hallucinates an incorrect query or missing parameter, ToolGuard will map exactly where the failure occurs before you push to production.

## Zero-Config Testing
The easiest way is using the CLI. ToolGuard will automatically find any `FunctionTool` instantiated in your script:
```bash
toolguard run query_engine.py
```

## Programmatic Usage
If you want to run assertions inside standard `pytest` scripts:
```python
from toolguard.integrations.llamaindex import guard_llamaindex_tool
from toolguard.core.chain import test_chain
from llama_index.core.tools import FunctionTool

def multiply(a: int, b: int) -> int:
    """Useful for multiplying numbers."""
    return a * b

llama_tool = FunctionTool.from_defaults(fn=multiply)

# Wrap it for Fuzzing!
guarded = guard_llamaindex_tool(llama_tool)

if __name__ == "__main__":
    report = test_chain([guarded], assert_reliability=0.95)
    print(report.summary())
```
