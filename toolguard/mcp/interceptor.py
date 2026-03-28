"""
toolguard.mcp.interceptor
~~~~~~~~~~~~~~~~~~~~~~~~~~
The 6-layer security pipeline for MCP tool calls.

Applies the following checks to every `tools/call` request:
  1. Policy Check     — Is this tool blocked?
  2. Risk Tier Gate   — Does this tool require human approval?
  3. Injection Scan   — Does the payload contain prompt injection?
  4. Rate Limiting    — Has this tool exceeded its call frequency?
  5. Semantic Policy  — Does the argument content violate semantic rules?
  6. Trace Logging    — Record the call in the execution DAG.
"""

from __future__ import annotations

import json
import os
import sys
import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.semantic import SemanticEngine, SessionContext


# ──────────────────────────────────────────────
#  Interceptor Result
# ──────────────────────────────────────────────

@dataclass
class InterceptResult:
    """Result of the interceptor pipeline."""
    allowed: bool
    reason: str = ""
    layer: str = ""  # Which layer blocked it


# ──────────────────────────────────────────────
#  Rate Limiter (sliding window)
# ──────────────────────────────────────────────

class RateLimiter:
    """Simple per-tool sliding-window rate limiter."""

    def __init__(self):
        self._calls: dict[str, list[float]] = {}

    def check(self, tool_name: str, limit: int) -> bool:
        """Returns True if the call is allowed, False if rate-limited."""
        now = time.time()
        window_start = now - 60.0  # 1-minute window

        if tool_name not in self._calls:
            self._calls[tool_name] = []

        # Prune old entries
        self._calls[tool_name] = [
            t for t in self._calls[tool_name] if t > window_start
        ]

        if len(self._calls[tool_name]) >= limit:
            return False

        self._calls[tool_name].append(now)
        return True


# ──────────────────────────────────────────────
#  Prompt Injection Scanner (lightweight)
# ──────────────────────────────────────────────

# Common prompt injection patterns
_INJECTION_PATTERNS = [
    r"\[SYSTEM\s*OVERRIDE\]",
    r"\[INST\]",
    r"<\|im_start\|>",
    r"<\|system\|>",
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"forget\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?(above|previous)",
    r"new\s+system\s+prompt",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def _scan_value_for_injection(value: Any, depth: int = 0) -> str | None:
    """Recursively scan a value for prompt injection patterns.
    
    Returns the matched pattern string if found, None otherwise.
    Uses depth-first search to traverse nested structures.
    """
    if depth > 20:  # Prevent infinite recursion
        return None

    if isinstance(value, str):
        text = value.casefold()
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(text):
                return pattern.pattern
        return None

    if isinstance(value, dict):
        for v in value.values():
            result = _scan_value_for_injection(v, depth + 1)
            if result:
                return result

    if isinstance(value, (list, tuple)):
        for item in value:
            result = _scan_value_for_injection(item, depth + 1)
            if result:
                return result

    # Scan object attributes (DFS into custom objects)
    if hasattr(value, "__dict__") and not isinstance(value, type):
        for v in vars(value).values():
            result = _scan_value_for_injection(v, depth + 1)
            if result:
                return result

    return None


# ──────────────────────────────────────────────
#  The 5-Layer Interceptor
# ──────────────────────────────────────────────

class MCPInterceptor:
    """Applies the ToolGuard security pipeline to an MCP tool call.
    
    Usage:
        interceptor = MCPInterceptor(policy)
        result = interceptor.intercept("delete_file", {"path": "/etc/passwd"})
        if not result.allowed:
            # Return JSON-RPC error to client
            ...
    """

    def __init__(self, policy: MCPPolicy, verbose: bool = False):
        self.policy = policy
        self.verbose = verbose
        self._rate_limiter = RateLimiter()
        self._trace_log: list[dict[str, Any]] = []
        self._semantic_engine = SemanticEngine.from_policy_dict(
            {"tools": {
                name: {"constraints": tp.constraints}
                for name, tp in policy.tools.items()
                if tp.constraints
            }}
        )
        self._session = SessionContext()

    def intercept(self, tool_name: str, arguments: dict[str, Any]) -> InterceptResult:
        """Run the full 6-layer security pipeline.
        
        Args:
            tool_name: The MCP tool name from the `tools/call` request.
            arguments: The arguments dict from the `tools/call` request.
            
        Returns:
            InterceptResult indicating whether the call is allowed or denied.
        """
        # ── Layer 1: Policy Check ──
        if self.policy.is_blocked(tool_name):
            self._log("BLOCKED", tool_name, "Tool is permanently blocked by policy")
            result = InterceptResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is blocked by security policy.",
                layer="policy",
            )
            self._emit_trace(tool_name, arguments, result)
            return result

        # ── Layer 2: Risk Tier Gate ──
        tier = self.policy.get_risk_tier(tool_name)
        if tier >= 2 and not self.policy.auto_approve:
            # Require human approval
            approved = self._request_approval(tool_name, arguments)
            if not approved:
                self._log("DENIED", tool_name, "Human denied tier-2 tool execution")
                result = InterceptResult(
                    allowed=False,
                    reason=f"Tool '{tool_name}' requires human approval (risk tier {tier}). Denied.",
                    layer="risk_tier",
                )
                self._emit_trace(tool_name, arguments, result)
                return result

        # ── Layer 3: Prompt Injection Scan ──
        if self.policy.should_scan_injection(tool_name):
            injection_match = _scan_value_for_injection(arguments)
            if injection_match:
                self._log("INJECTION", tool_name, f"Matched pattern: {injection_match}")
                result = InterceptResult(
                    allowed=False,
                    reason=f"Prompt injection detected in arguments for '{tool_name}'. Pattern: {injection_match}",
                    layer="injection",
                )
                self._emit_trace(tool_name, arguments, result)
                return result

        # ── Layer 4: Rate Limiting ──
        limit = self.policy.get_rate_limit(tool_name)
        if not self._rate_limiter.check(tool_name, limit):
            self._log("RATE_LIMITED", tool_name, f"Exceeded {limit} calls/min")
            result = InterceptResult(
                allowed=False,
                reason=f"Tool '{tool_name}' rate limited ({limit} calls/min exceeded).",
                layer="rate_limit",
            )
            self._emit_trace(tool_name, arguments, result)
            return result

        # ── Layer 5: Semantic Policy ──
        if self._semantic_engine.has_constraints(tool_name):
            sem_result = self._semantic_engine.evaluate(
                tool_name, arguments, self._session
            )
            if not sem_result.allowed:
                self._log("SEMANTIC", tool_name, sem_result.reason)
                result = InterceptResult(
                    allowed=False,
                    reason=f"[Semantic Policy] {sem_result.reason}",
                    layer="semantic",
                )
                self._emit_trace(tool_name, arguments, result)
                return result

        # ── Layer 6: Trace Logging ──
        self._session.record_call(tool_name, arguments)
        self._trace_log.append({
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": time.time(),
            "decision": "ALLOWED",
        })

        self._log("ALLOWED", tool_name, "All 6 layers passed")
        result = InterceptResult(allowed=True, layer="trace")
        self._emit_trace(tool_name, arguments, result)
        return result

    @property
    def trace(self) -> list[dict[str, Any]]:
        """Returns the complete execution trace log."""
        return list(self._trace_log)

    def _request_approval(self, tool_name: str, arguments: dict) -> bool:
        """Request human approval for a tier-2 tool via terminal."""
        try:
            print(
                f"\n🛡️  [ToolGuard MCP Proxy] APPROVAL REQUIRED\n"
                f"   Tool:      {tool_name}\n"
                f"   Arguments: {arguments}\n"
                f"   Risk Tier: 2 (destructive)\n",
                file=sys.stderr,
            )
            response = input("   Approve? [y/N]: ").strip().lower()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _emit_trace(self, tool_name: str, arguments: dict, result: InterceptResult) -> None:
        """Write a trace JSON file for the Obsidian Dashboard's SSE file watcher."""
        try:
            trace_dir = Path(".toolguard/mcp_traces")
            trace_dir.mkdir(parents=True, exist_ok=True)

            trace_data = {
                "tool": tool_name,
                "arguments": arguments,
                "timestamp": time.time(),
                "decision": "ALLOWED" if result.allowed else "BLOCKED",
                "layer": result.layer,
                "reason": result.reason,
            }

            file_path = trace_dir / f"trace_{int(time.time() * 1000)}.json"
            file_path.write_text(json.dumps(trace_data), encoding="utf-8")
        except Exception:
            pass

    def _log(self, status: str, tool_name: str, detail: str) -> None:
        """Log interceptor decisions to stderr if verbose mode is on."""
        if self.verbose:
            print(
                f"  🛡️  [{status}] {tool_name}: {detail}",
                file=sys.stderr,
            )