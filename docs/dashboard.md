# Live Web Dashboard

ToolGuard ships with a zero-dependency, real-time web dashboard for monitoring agent tool calls and security events.

## Quick Start

```bash
toolguard dashboard
```

The dashboard launches at `http://127.0.0.1:8557` with these features:

## Features

### Sentinel HUD
A real-time diagnostic LED array showing the status of all 6 interceptor layers:

| LED | Layer | Meaning |
|-----|-------|---------|
| `L1:POL` | Policy | Tool is allowed/blocked by config |
| `L2:RSK` | Risk-Tier | Human approval gate |
| `L3:INJ` | Injection | Prompt injection scanner |
| `L4:RAT` | Rate-Limit | Call frequency throttle |
| `L5:SEM` | Semantic | Context-aware policy engine |
| `L6:TRC` | Trace | Execution DAG logger |

Green = layer passed. Red = layer intercepted a threat.

### Trace Stream
The left pane shows a live timeline of all tool calls with their ALLOW/BLOCKED status, streamed in real-time via Server-Sent Events (SSE).

### Payload Inspector
Click any trace in the stream to open the right pane inspector, which displays:

- **Decision status** (Allowed or Blocked)
- **Arguments Payload** (the exact JSON the agent sent)
- **Interceptor Layer** (which layer caught it)
- **Raw Trace Object** (full JSON for debugging)

### Global Kill-Switch
The `[ SECURE ]` toggle in the HUD header instantly freezes all agent execution when switched to `[ LOCKED ]`.

## CLI Options

```bash
# Custom port
toolguard dashboard --port 9000

# Don't auto-open browser
toolguard dashboard --no-browser
```

## Architecture

The dashboard is built with:
- **Backend**: FastAPI with Server-Sent Events (SSE)
- **Frontend**: Vanilla HTML/CSS/JS (zero npm dependencies)
- **Data**: Reads trace JSON files from `.toolguard/mcp_traces/`
