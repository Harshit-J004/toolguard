# Getting Started

Install ToolGuard and test your first tool chain in under 5 minutes.

## Installation

```bash
pip install py-toolguard
```

## Step 1: Wrap Your Tools

Use `@create_tool` to add automatic validation to any function:

```python
from toolguard import create_tool

@create_tool(schema="auto")
def get_weather(location: str, units: str = "metric") -> dict:
    """Fetch weather data for a location."""
    # Your real API call goes here
    return {"temp": 22.5, "units": units, "conditions": "sunny"}

@create_tool(schema="auto")
def process_forecast(temp: float, conditions: str = "") -> dict:
    """Transform raw weather into a forecast."""
    severity = "normal" if temp < 35 else "heat_warning"
    return {"forecast": f"{temp}°, {conditions}", "severity": severity}
```

That's it — inputs and outputs are now validated automatically via Pydantic.

## Step 2: Test the Chain

```python
from toolguard import test_chain

report = test_chain(
    [get_weather, process_forecast],
    base_input={"location": "NYC", "units": "metric"},
    test_cases=["happy_path", "null_handling", "malformed_data"],
    assert_reliability=0.90,
)
```

ToolGuard will:

1. Generate edge-case inputs (nulls, wrong types, missing fields, etc.)
2. Run each input through your chain
3. Catch and analyze cascading failures
4. Produce a detailed report

## Step 3: Score & Gate

```python
from toolguard import score_chain

score = score_chain(report)
print(score.summary())

# Output:
# Reliability:  87.5%
# Risk Level:   MEDIUM
# Deploy:       WARN
```

## Step 4: Add to CI/CD

Create a chain config YAML file:

```yaml
chain:
  name: weather_pipeline
  tools:
    - module: my_tools
      function: get_weather
    - module: my_tools
      function: process_forecast

testing:
  test_cases: [happy_path, null_handling, type_mismatch]
  iterations: 10
  reliability_threshold: 0.95
```

Then run in your pipeline:

```bash
toolguard test --chain weather_pipeline.yaml
```

Exit code 1 = below threshold. Your CI fails, your agent stays safe.

## Next Steps

- [Chain Testing](chain-testing.md) — Deep dive into all 8 test case types
- [Scoring](scoring.md) — Understanding risk levels and deploy gates
- [Observability](observability.md) — OpenTelemetry tracing for production
