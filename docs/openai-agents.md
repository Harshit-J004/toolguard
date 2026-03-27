# OpenAI Agents SDK Integration

ToolGuard natively integrates with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) `@function_tool` decorator.

## Zero-Config Testing
ToolGuard CLI automatically detects OpenAI Agents SDK tools in your scripts:
```bash
toolguard run my_openai_agent.py
```

## Programmatic Usage
```python
from agents import function_tool
from toolguard.integrations.openai_agents import guard_openai_agents_tool
from toolguard.core.chain import test_chain

@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Weather in {city}: Sunny"

# Wrap it for fuzzing
guarded = guard_openai_agents_tool(get_weather)

if __name__ == "__main__":
    report = test_chain([guarded], assert_reliability=0.95)
    print(report.summary())
```

## How It Works

ToolGuard extracts the underlying Python function via the `.fn` or `._func` attribute on the OpenAI Agents SDK tool object. The tool's `name` and `description` metadata are automatically preserved.
