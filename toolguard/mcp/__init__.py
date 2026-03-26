"""
toolguard.mcp
~~~~~~~~~~~~~
MCP Security Proxy — Runtime firewall for the Model Context Protocol.

Intercepts JSON-RPC 2.0 `tools/call` messages between any MCP client
and any MCP server, applying ToolGuard's 5-layer security pipeline:
  1. Policy enforcement (blocked tools)
  2. Risk-tier gating (human approval for destructive tools)
  3. Schema validation (Pydantic type-checking on arguments)
  4. Prompt injection scanning (recursive DFS memory scan)
  5. Rate limiting (per-tool call frequency caps)
"""

from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.interceptor import MCPInterceptor
from toolguard.mcp.proxy import MCPProxy

__all__ = ["MCPPolicy", "MCPInterceptor", "MCPProxy"]
