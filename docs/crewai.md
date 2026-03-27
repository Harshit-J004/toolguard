# CrewAI Integration

ToolGuard natively integrates with [CrewAI](https://github.com/crewAIInc/crewAI) tools — both `BaseTool` subclasses and `@tool` decorated functions.

## Zero-Config Testing
ToolGuard CLI automatically detects CrewAI tools in your scripts:
```bash
toolguard run my_crewai_agent.py
```

## Programmatic Usage
```python
from crewai_tools import SomeCrewTool
from toolguard.integrations.crewai import guard_crewai_tool
from toolguard.core.chain import test_chain

# Wrap a CrewAI tool for fuzzing
guarded = guard_crewai_tool(SomeCrewTool())

if __name__ == "__main__":
    report = test_chain([guarded], assert_reliability=0.95)
    print(report.summary())
```

## How It Works

ToolGuard extracts the underlying Python function from your CrewAI tool by checking for:

1. `.func` attribute (from `@tool` decorated functions)
2. `._run()` method (from `BaseTool` subclasses)
3. `._arun()` method (async tools)

The extracted function is then wrapped in a `GuardedTool` with the original tool's `name` and `description` metadata preserved.
