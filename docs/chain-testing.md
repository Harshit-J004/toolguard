# Chain Testing

Chain testing is ToolGuard's killer feature. It tests multi-tool chains for cascading failures by running them against generated edge-case inputs.

## How It Works

```python
from toolguard import test_chain

report = test_chain(
    [tool_a, tool_b, tool_c],
    base_input={"key": "value"},
    test_cases=["happy_path", "null_handling"],
    iterations=10,
    assert_reliability=0.95,
)
```

ToolGuard generates test inputs for each case type, then runs them through the chain. If Tool A's output breaks Tool B's input, ToolGuard captures the exact cascade path and provides a fix suggestion.

## 8 Built-In Test Case Types

| Test Case | What It Does | What It Catches |
|---|---|---|
| `happy_path` | Runs with valid base input | Baseline failures |
| `null_handling` | Sets each field to `None` | Null propagation bugs |
| `malformed_data` | Swaps types (str→int, int→str) | Type assumption errors |
| `empty_input` | Sends `{}`, `""` values | Missing default handling |
| `type_mismatch` | Converts str→list, int→str | Implicit type expectations |
| `large_payload` | 10,000x strings, 10^18 ints | Buffer overflows, timeouts |
| `missing_fields` | Removes one field at a time | Required field assumptions |
| `extra_fields` | Adds unexpected fields | Strict vs. flexible parsing |

## Understanding the Report

```python
print(report.summary())
```

```
Chain Test Report: get_weather → process_forecast → send_alert
══════════════════════════════════════════════════
  ✓ 47 passed
  ✗ 3 failed
  📊 94.0% reliability (threshold: 95%)

Top Failures:
  1. [2x] process_forecast → SchemaValidationError
     Root cause: process_forecast received null/None value
     💡 Add null check: if data is None: return default_value()

  2. [1x] send_alert → KeyError
     Root cause: send_alert tried to access a missing key
     💡 Use data.get('key', default) instead of data['key']

Result: ❌ BELOW THRESHOLD
```

## Failure Analysis

Every failure includes:

- **Step number** — which tool in the chain broke
- **Cascade path** — `get_weather ✓ → process_forecast ✗`
- **Root cause** — inferred from error type and context
- **Suggestion** — actionable fix you can apply immediately

## CI/CD Integration

```yaml
# .github/workflows/toolguard.yml
- name: Test tool chain reliability
  run: toolguard test --chain my_chain.yaml
```

Exit code 0 = passed threshold. Exit code 1 = failed. Works with any CI system.
