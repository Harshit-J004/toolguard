# OpenAI Swarm Integration

ToolGuard supports natively fuzzing the `functions` payload assigned to any [OpenAI Swarm](https://github.com/openai/swarm) `Agent`.

## Zero-Config Testing
ToolGuard CLI will automatically detect any instantiated `Agent` variables, extract all of its functions, and run them through the Fuzzing Engine:
```bash
toolguard run my_swarm_node.py
```

## Programmatic Usage
```python
from swarm import Agent
from toolguard.integrations.swarm import guard_swarm_agent
from toolguard.core.chain import test_chain

def fetch_logs(user_id: int) -> str:
    return "Logs..."

agent = Agent(
    name="Log Fetcher",
    functions=[fetch_logs]
)

# Extract and fuzz all functions assigned to the Swarm Agent
if __name__ == "__main__":
    tools = guard_swarm_agent(agent)
    report = test_chain(tools, assert_reliability=0.95)
    print(report.summary())
```
