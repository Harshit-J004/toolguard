# MCP Security Proxy

ToolGuard includes a transparent, runtime security proxy for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## The Problem

MCP is the universal standard for connecting LLMs to external tools — but the protocol has **zero native security**. Any tool call from Claude, Gemini, or GPT passes through as raw, unguarded JSON-RPC traffic.

## The Solution

ToolGuard's MCP Proxy sits between any MCP client and server, applying a **7-Layer Interceptor Pipeline** to every `tools/call` request:

| Layer | Name | What It Does |
|-------|------|-------------|
| L1 | **Policy** | Hard-blocks tools permanently forbidden by your YAML config |
| L2 | **Risk-Tier** | Pauses Tier-2 destructive tools and requires human approval |
| L3 | **Injection** | Recursive DFS scan for prompt injection patterns in arguments |
| L4 | **Rate-Limit** | Per-tool call frequency caps (sliding 1-minute window) |
| L5 | **Semantic** | Context-aware authorization — regex deny, path patterns, session scope |
| L6 | **Drift** | Schema drift detection — compares live payloads against frozen structural baselines |
| L7 | **Trace** | Full execution DAG logging for audit and replay |

## Quick Start

```bash
toolguard proxy --upstream "python database_server.py" --policy security.yaml
```

## Policy Configuration

```yaml
# security.yaml
defaults:
  risk_tier: 0
  scan_injection: true
  rate_limit: 30

tools:
  delete_database:
    blocked: true
  execute_sql:
    constraints:
      - type: regex_deny
        field: query
        patterns: ["DROP\\s+TABLE", "DELETE\\s+FROM"]
        reason: "Destructive SQL operations are forbidden"
  shutdown_server:
    risk_tier: 2
```

## Programmatic Usage

```python
from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.interceptor import MCPInterceptor

policy = MCPPolicy.from_yaml("security.yaml")
interceptor = MCPInterceptor(policy, verbose=True)

result = interceptor.intercept("execute_sql", {"query": "DROP TABLE users"})
if not result.allowed:
    print(f"Blocked at layer: {result.layer}")
    print(f"Reason: {result.reason}")
```
