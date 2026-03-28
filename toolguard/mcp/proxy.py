"""
toolguard.mcp.proxy
~~~~~~~~~~~~~~~~~~~
The core MCP Security Proxy engine.

Operates at the raw JSON-RPC 2.0 transport layer — no dependency on the
`mcp` Python SDK. This makes ToolGuard compatible with MCP servers written
in any language (Python, TypeScript, Go, Rust).

Architecture:
  [MCP Client] --stdin/stdout--> [ToolGuard Proxy] --stdin/stdout--> [MCP Server subprocess]

The proxy:
  1. Spawns the upstream MCP server as a subprocess
  2. Reads JSON-RPC messages from stdin (client side)
  3. Inspects each message for `tools/call` method
  4. Applies the interceptor security pipeline
  5. Forwards clean requests to the upstream server
  6. Relays responses back to the client
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from typing import Any

from toolguard.mcp.interceptor import MCPInterceptor
from toolguard.mcp.policy import MCPPolicy


class MCPProxy:
    """Transparent JSON-RPC proxy for MCP with embedded security.
    
    Usage:
        policy = MCPPolicy.from_yaml_file("policy.yaml")
        proxy = MCPProxy(upstream_cmd=["python", "my_server.py"], policy=policy)
        proxy.start()  # Blocks until stdin closes
    """

    def __init__(
        self,
        upstream_cmd: list[str],
        policy: MCPPolicy | None = None,
        verbose: bool = False,
        log_dir: str | None = None,
    ):
        self.upstream_cmd = upstream_cmd
        self.policy = policy or MCPPolicy.default()
        self.verbose = verbose
        self.log_dir = log_dir
        self.interceptor = MCPInterceptor(self.policy, verbose=verbose)
        self._upstream_process: subprocess.Popen | None = None
        self._stats = {"forwarded": 0, "blocked": 0, "total": 0}

    def start(self) -> None:
        """Start the proxy. Blocks until stdin is closed by the client."""
        self._log_info("Starting ToolGuard MCP Security Proxy...")
        self._log_info(f"Upstream: {' '.join(self.upstream_cmd)}")
        self._log_info(f"Policy: {len(self.policy.tools)} tool-specific rules loaded")
        self._log_info("")

        # Spawn the upstream MCP server
        try:
            self._upstream_process = subprocess.Popen(
                self.upstream_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                bufsize=1,  # Line-buffered
            )
        except FileNotFoundError:
            self._log_error(f"Could not start upstream server: {self.upstream_cmd}")
            sys.exit(1)

        # Start relay thread: upstream stdout → our stdout
        relay_thread = threading.Thread(
            target=self._relay_upstream_to_client,
            daemon=True,
        )
        relay_thread.start()

        # Main loop: our stdin → interceptor → upstream stdin
        try:
            self._process_client_messages()
        except KeyboardInterrupt:
            self._log_info("\nProxy shutting down...")
        finally:
            self._shutdown()

    def _process_client_messages(self) -> None:
        """Read JSON-RPC messages from stdin and process them."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            self._stats["total"] += 1

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Not valid JSON — forward as-is (might be a transport header)
                self._forward_to_upstream(line)
                continue

            # Check if this is a tools/call request
            method = msg.get("method", "")
            if method == "tools/call":
                self._handle_tool_call(msg, line)
            else:
                # Not a tool call — forward transparently
                self._forward_to_upstream(line)
                self._stats["forwarded"] += 1

    def _handle_tool_call(self, msg: dict[str, Any], raw_line: str) -> None:
        """Apply the security pipeline to a tools/call request."""
        params = msg.get("params", {})
        tool_name = params.get("name", "<unknown>")
        arguments = params.get("arguments", {})
        request_id = msg.get("id")

        # Run the 6-layer interceptor
        result = self.interceptor.intercept(tool_name, arguments)

        if result.allowed:
            # ✅ Clean — forward to upstream
            self._forward_to_upstream(raw_line)
            self._stats["forwarded"] += 1
        else:
            # 🛡️ Blocked — return JSON-RPC error directly to client
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32600,  # Invalid Request
                    "message": f"[ToolGuard] {result.reason}",
                    "data": {
                        "layer": result.layer,
                        "tool": tool_name,
                        "blocked_by": "toolguard-mcp-proxy",
                    },
                },
            }
            self._send_to_client(json.dumps(error_response))
            self._stats["blocked"] += 1

    def _forward_to_upstream(self, line: str) -> None:
        """Send a raw line to the upstream MCP server's stdin."""
        if self._upstream_process and self._upstream_process.stdin:
            try:
                self._upstream_process.stdin.write(line + "\n")
                self._upstream_process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._log_error("Upstream server pipe broken")

    def _relay_upstream_to_client(self) -> None:
        """Read lines from upstream stdout and relay to our stdout (client)."""
        if not self._upstream_process or not self._upstream_process.stdout:
            return

        try:
            for line in self._upstream_process.stdout:
                self._send_to_client(line.rstrip("\n"))
        except (BrokenPipeError, OSError):
            pass

    def _send_to_client(self, line: str) -> None:
        """Write a line to our stdout (the MCP client)."""
        try:
            print(line, flush=True)
        except (BrokenPipeError, OSError):
            pass

    def _shutdown(self) -> None:
        """Gracefully terminate the upstream server."""
        if self._upstream_process:
            self._upstream_process.terminate()
            try:
                self._upstream_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._upstream_process.kill()

        # Print summary
        self._log_info("")
        self._log_info("=" * 50)
        self._log_info("  ToolGuard MCP Proxy Session Summary")
        self._log_info("=" * 50)
        self._log_info(f"  Total messages:  {self._stats['total']}")
        self._log_info(f"  Forwarded:       {self._stats['forwarded']}")
        self._log_info(f"  Blocked:         {self._stats['blocked']}")
        self._log_info(f"  Trace entries:   {len(self.interceptor.trace)}")
        self._log_info("=" * 50)

        # Save trace log if log_dir specified
        if self.log_dir and self.interceptor.trace:
            self._save_trace_log()

    def _save_trace_log(self) -> None:
        """Persist the execution trace to disk."""
        import os
        os.makedirs(self.log_dir, exist_ok=True)
        trace_path = os.path.join(
            self.log_dir,
            f"mcp_trace_{int(time.time())}.json",
        )
        with open(trace_path, "w") as f:
            json.dump(self.interceptor.trace, f, indent=2, default=str)
        self._log_info(f"  Trace saved: {trace_path}")

    def _log_info(self, msg: str) -> None:
        """Log to stderr (never pollute stdout — that's the MCP transport)."""
        print(f"  🛡️  {msg}", file=sys.stderr)

    def _log_error(self, msg: str) -> None:
        print(f"  ❌  {msg}", file=sys.stderr)
