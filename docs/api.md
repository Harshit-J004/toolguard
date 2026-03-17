# API Reference

## Core

### `@create_tool(schema="auto")`

Decorator that wraps a function with automatic Pydantic validation.

```python
from toolguard import create_tool

@create_tool(schema="auto")
def my_tool(x: int, y: str = "default") -> dict:
    return {"result": x, "label": y}
```

**Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `schema` | `str \| dict` | `"auto"` | `"auto"` generates from type hints |
| `input_model` | `BaseModel` | `None` | Explicit Pydantic input model |
| `output_model` | `BaseModel` | `None` | Explicit Pydantic output model |
| `version` | `str` | `"1.0.0"` | Tool version string |

**Returns:** `GuardedTool` — callable wrapper with `.schema`, `.stats`, `.unwrap()`

---

### `test_chain(chain, **kwargs)`

Test a tool chain end-to-end for reliability.

```python
from toolguard import test_chain

report = test_chain(
    [tool_a, tool_b],
    base_input={"key": "val"},
    test_cases=["happy_path", "null_handling"],
    iterations=10,
    assert_reliability=0.95,
)
```

**Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `chain` | `list[Callable]` | required | Ordered list of tools |
| `base_input` | `dict` | `{}` | Base input for test generation |
| `test_cases` | `list[str]` | all 4 defaults | Test case types to run |
| `iterations` | `int` | `5` | Repeat count for happy_path |
| `assert_reliability` | `float` | `0.95` | Raise if below this |
| `chain_name` | `str` | auto | Human-readable chain name |

**Returns:** `ChainTestReport`
**Raises:** `AssertionError` if reliability < threshold

---

### `score_chain(report)`

Generate a reliability score from a chain test report.

```python
from toolguard import score_chain

score = score_chain(report)
print(score.reliability)  # 0.875
print(score.risk_level)   # RiskLevel.MEDIUM
print(score.deploy_recommendation)  # DeployRecommendation.WARN
```

**Returns:** `ReliabilityScore`

---

## Resilience

### `@with_retry(policy)`

```python
from toolguard.core.retry import with_retry, RetryPolicy

@with_retry(RetryPolicy(max_retries=3, backoff_base=0.5))
def flaky_api(data: dict) -> dict: ...
```

### `@with_circuit_breaker(breaker)`

```python
from toolguard.core.retry import CircuitBreaker, with_circuit_breaker

breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)

@with_circuit_breaker(breaker)
def external_service(data: dict) -> dict: ...
```

---

## Integrations

### LangChain

```python
from toolguard.integrations.langchain import guard_langchain_tool
guarded = guard_langchain_tool(my_langchain_tool)
```

### CrewAI

```python
from toolguard.integrations.crewai import guard_crewai_tool
guarded = guard_crewai_tool(my_crew_tool)
```

### OpenAI Function Calling

```python
from toolguard.integrations.openai_func import to_openai_function
schema = to_openai_function(my_tool)
```
