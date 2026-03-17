# Observability

ToolGuard integrates with OpenTelemetry to trace every tool call in production.

## Setup

```python
from toolguard.core.tracer import init_tracing, trace_tool

# Initialize (connects to your existing observability stack)
init_tracing(service_name="my-agent")
```

## Tracing Tools

```python
@trace_tool
def my_api_call(data: dict) -> dict:
    # This call is now traced with:
    # - tool.name
    # - tool.input
    # - tool.output (truncated)
    # - tool.success (bool)
    # - Exceptions recorded automatically
    return api.call(data)
```

## What Gets Traced

Each tool call emits a span with:

| Attribute | Description |
|---|---|
| `tool.name` | Function name |
| `tool.input` | Input arguments (stringified) |
| `tool.output` | Return value (truncated to 200 chars) |
| `tool.success` | Boolean success/failure |
| Exception | Full exception recorded on failure |

## Backends

Works with any OpenTelemetry-compatible backend:

- **Jaeger** — open-source distributed tracing
- **Zipkin** — lightweight tracing
- **Datadog** — enterprise APM
- **Grafana Tempo** — scalable tracing
- **AWS X-Ray** — cloud-native tracing

## CLI Observability

```bash
# View tool statistics
toolguard observe --tools my_tools.py

# Demo mode (simulated data)
toolguard observe --demo
```
