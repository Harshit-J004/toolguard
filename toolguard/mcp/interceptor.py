"""
toolguard.mcp.interceptor
~~~~~~~~~~~~~~~~~~~~~~~~~~
The 7-layer security pipeline for MCP tool calls.

Applies the following checks to every `tools/call` request:
  1. Policy Check     — Is this tool blocked?
  2. Risk Tier Gate   — Does this tool require human approval?
  3. Injection Scan   — Does the payload contain prompt injection?
  4. Rate Limiting    — Has this tool exceeded its call frequency?
  5. Semantic Policy  — Does the argument content violate semantic rules?
  6. Schema Drift     — Does the payload match the frozen baseline structure?
  7. Trace Logging    — Record the call in the execution DAG.
"""

from __future__ import annotations

import json
import os
import sys
import time
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from toolguard.mcp.policy import MCPPolicy
from toolguard.mcp.semantic import SemanticEngine, SessionContext
from toolguard.core.drift import detect_drift, SchemaFingerprint
from toolguard.core.drift_store import FingerprintStore


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
        self._lock = threading.Lock()
        self._cache_file = Path(".toolguard/rate_limits.json")
        self._load_cache()

    def _load_cache(self) -> None:
        try:
            if self._cache_file.exists():
                self._calls = json.loads(self._cache_file.read_text("utf-8"))
        except Exception:
            self._calls = {}

    def _save_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(json.dumps(self._calls), "utf-8")
        except Exception:
            pass

    def check(self, tool_name: str, limit: int) -> bool:
        """Returns True if the call is allowed, False if rate-limited.
        
        Hardened: Uses normalized tool names and explicit thread-locks to 
        ensure atomic window updates under high production load.
        """
        name = tool_name.strip().casefold()
        now = time.time()
        window_start = now - 60.0  # 1-minute window

        with self._lock:
            if name not in self._calls:
                self._calls[name] = []

            # Prune old entries
            self._calls[name] = [
                t for t in self._calls[name] if t > window_start
            ]

            if len(self._calls[name]) >= limit:
                self._save_cache()
                return False

            self._calls[name].append(now)
            self._save_cache()
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
    # Shell Injection / Command Execution Attack Patterns (2026 Rigor)
    r"curl\s+.*\|\s+bash",
    r"wget\s+.*\|\s+sh",
    r"rm\s+-rf\s+(/|\.)",
    r"DROP\s+TABLE",
    r"chmod\s+777",
    r"cat\s+/etc/passwd",
    r"nc\s+-e\s+/bin/sh",
    r"powershell\s+-Command",
    r"base64\s+-d\s+.*\|\s+bash",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


# Maximum recursion depth for security scans to prevent Stack-Buster DoS
_MAX_SCAN_DEPTH = 50


def _scan_value_for_injection(
    value: Any, visited: set | None = None, depth: int = 0
) -> str | None:
    """Recursively scan a value for prompt injection patterns.
    
    Returns the matched pattern string if found, None otherwise.
    Uses a highly durable depth-first search memory scan that closes
    zero-day structural evasion blind spots.
    """
    if visited is None:
        visited = set()
    
    # 0. DoS Protection: Depth Limit
    if depth > _MAX_SCAN_DEPTH:
        return "[DEPTH_LIMIT_EXCEEDED]"

    obj_id = id(value)
    if obj_id in visited:
        return None
    visited.add(obj_id)

    # 1. String Scan (Case-Insensitive)
    if isinstance(value, str):
        text = value.casefold()
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(text):
                return pattern.pattern
        return None

    # 2. Dictionary Scan (Keys and Values)
    if isinstance(value, dict):
        for k, v in value.items():
            result = _scan_value_for_injection(k, visited, depth + 1) or \
                     _scan_value_for_injection(v, visited, depth + 1)
            if result: return result
        return None

    # 3. Iterable Scan (Fragmentation Defense)
    if isinstance(value, (list, tuple, set)):
        # Detect and Defeat Fragmentation Attacks:
        # If the iterable is a sequence of characters or very short strings,
        # we join them to detect patterns that are split across elements.
        if len(value) > 1:
            try:
                # Optimized join for homogenous character sequences
                if all(isinstance(i, str) and len(i) <= 2 for i in value):
                    joined = "".join(value).casefold()
                    for pattern in _COMPILED_PATTERNS:
                        if pattern.search(joined):
                            return pattern.pattern
            except Exception:
                pass

        for item in value:
            result = _scan_value_for_injection(item, visited, depth + 1)
            if result: return result
        return None

    # 4. Binary Stream Scan (Multi-Encoding Support)
    if isinstance(value, (bytes, bytearray)):
        for encoding in ["utf-8", "utf-16", "latin-1"]:
            try:
                text = value.decode(encoding, errors="ignore").casefold()
                for pattern in _COMPILED_PATTERNS:
                    if pattern.search(text):
                        return pattern.pattern
            except Exception:
                continue
        return None

    # 5. Object Scan (__dict__ and __slots__ Support)
    if not isinstance(value, type):
        # Scan __dict__ (Standard objects)
        if hasattr(value, "__dict__"):
            result = _scan_value_for_injection(vars(value), visited, depth + 1)
            if result: return result
        
        # Scan __slots__ (High-performance objects)
        if hasattr(value, "__slots__"):
            slots = value.__slots__
            if isinstance(slots, str): slots = (slots,)
            for slot in slots:
                try:
                    attr_val = getattr(value, slot)
                    result = _scan_value_for_injection(attr_val, visited, depth + 1)
                    if result: return result
                except AttributeError:
                    continue

    # 6. Fallback Stringification Scan
    # Catch-all to prevent evasion via custom __str__ logic.
    try:
        text = str(value).casefold()
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(text):
                return pattern.pattern
    except Exception:
        pass

    return None


# ──────────────────────────────────────────────
#  The 7-Layer Interceptor
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
        # Defense #1: Global stdin lock prevents thread race conditions
        self._stdin_lock = threading.Lock()
        # Defense #4: Approval cache for Tier 2 (tool_name -> expiry timestamp)
        self._approval_cache: dict[str, float] = {}
        self._approval_cache_lock = threading.Lock()

    def intercept(self, tool_name: str, arguments: dict[str, Any]) -> InterceptResult:
        """Run the full 7-layer security pipeline.
        
        Args:
            tool_name: The MCP tool name from the `tools/call` request.
            arguments: The arguments dict from the `tools/call` request.
            
        Returns:
            InterceptResult indicating whether the call is allowed or denied.
        """
        start_time = time.perf_counter()

        # Hardness Lockdown: Normalize tool name at entry point to prevent 
        # protocol-level evasion across all 7 layers.
        # Layer 7 Forensic Preservation: Original casing must be logged for auditing.
        original_tool_name = tool_name
        tool_name = tool_name.strip().casefold()

        # ── Layer 1: Policy Check ──
        if self.policy.is_blocked(tool_name):
            self._log("BLOCKED", tool_name, "Tool is permanently blocked by policy")
            result = InterceptResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is blocked by security policy.",
                layer="policy",
            )
            self._emit_trace(original_tool_name, arguments, result,
                             latency_ms=(time.perf_counter() - start_time) * 1000)
            return result

        # ── Layer 2: Risk Tier Gate (4-Tier Architecture) ──
        tier = self.policy.get_risk_tier(tool_name)
        tool_policy = self.policy.get_tool_policy(tool_name)

        # Tier 4: Forbidden — always deny, no override, no env bypass
        if tier >= 4:
            self._log("FORBIDDEN", tool_name, f"Tool is forbidden (risk tier {tier}). No override.")
            result = InterceptResult(
                allowed=False,
                reason=f"Tool '{tool_name}' is forbidden (risk tier {tier}). No override possible.",
                layer="risk_tier",
            )
            self._emit_trace(original_tool_name, arguments, result,
                             latency_ms=(time.perf_counter() - start_time) * 1000)
            return result

        # Tier 3: Critical — double-confirm (type tool name). Ignores auto_approve.
        if tier == 3:
            approved = self._request_critical_approval(tool_name, arguments)
            if not approved:
                self._log("DENIED", tool_name, f"Critical tool denied (risk tier {tier}). Double-confirm failed.")
                result = InterceptResult(
                    allowed=False,
                    reason=f"Tool '{tool_name}' requires critical double-confirmation (risk tier {tier}). Denied.",
                    layer="risk_tier",
                )
                self._emit_trace(original_tool_name, arguments, result,
                                 latency_ms=(time.perf_counter() - start_time) * 1000)
                return result

        # Tier 2: Restricted — human approval with timeout + caching. Respects auto_approve.
        elif tier == 2 and not self.policy.auto_approve:
            # Check approval cache first
            if not self._check_approval_cache(tool_name):
                timeout = tool_policy.approval_timeout
                approved = self._request_approval(tool_name, arguments, tier, timeout)
                if not approved:
                    self._log("DENIED", tool_name, f"Restricted tool denied (risk tier {tier}).")
                    result = InterceptResult(
                        allowed=False,
                        reason=f"Tool '{tool_name}' requires human approval (risk tier {tier}). Denied.",
                        layer="risk_tier",
                    )
                    self._emit_trace(original_tool_name, arguments, result,
                                     latency_ms=(time.perf_counter() - start_time) * 1000)
                    return result
                # Cache the approval if TTL > 0
                ttl = tool_policy.approval_ttl
                if ttl > 0:
                    self._cache_approval(tool_name, ttl)

        # ── Layer 3: Prompt Injection Scan ──
        if self.policy.should_scan_injection(tool_name):
            injection_match = _scan_value_for_injection(arguments)
            if injection_match:
                if injection_match == "[DEPTH_LIMIT_EXCEEDED]":
                    reason = f"Security scan depth limit exceeded for '{tool_name}'. Potential Stack-Buster DoS attempt."
                    layer = "injection_dos"
                else:
                    reason = f"Prompt injection detected in arguments for '{tool_name}'. Pattern: {injection_match}"
                    layer = "injection"

                self._log("INJECTION", tool_name, reason)
                result = InterceptResult(
                    allowed=False,
                    reason=reason,
                    layer=layer,
                )
                self._emit_trace(original_tool_name, arguments, result, 
                                 latency_ms=(time.perf_counter() - start_time) * 1000)
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
            self._emit_trace(original_tool_name, arguments, result,
                             latency_ms=(time.perf_counter() - start_time) * 1000)
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
                self._emit_trace(original_tool_name, arguments, result, 
                                 latency_ms=(time.perf_counter() - start_time) * 1000)
                return result

        # ── Layer 6: Schema Drift ──
        # Execute the static-typed baseline diffing engine against incoming execution payloads
        with FingerprintStore() as store:
            baseline = store.get_latest_fingerprint_for_tool(tool_name)
            
        if baseline:

            drift_report = detect_drift(baseline, arguments)
            
            # Critical enforcement block
            if drift_report.has_drift and drift_report.severity in ("critical", "major"):
                bad_drifts = [d for d in drift_report.drifts if d.severity in ("critical", "major")]
                reason_str = ", ".join([f"[{d.drift_type}] {d.field}" for d in bad_drifts])
                
                self._log("DRIFT", tool_name, f"Structural drift detected: {reason_str}")
                result = InterceptResult(
                    allowed=False,
                    reason=f"Silent prompt execution drift detected ({drift_report.severity.upper()}): {reason_str}",
                    layer="drift",
                )
                self._emit_trace(original_tool_name, arguments, result, 
                                 latency_ms=(time.perf_counter() - start_time) * 1000)
                return result

        # ── Layer 7: Trace Logging ──
        self._session.record_call(tool_name, arguments)
        self._trace_log.append({
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": time.time(),
            "decision": "ALLOWED",
        })

        self._log("ALLOWED", tool_name, "All 7 layers passed")
        result = InterceptResult(allowed=True, layer="trace")
        self._emit_trace(original_tool_name, arguments, result,
                         latency_ms=(time.perf_counter() - start_time) * 1000)
        return result

    @property
    def trace(self) -> list[dict[str, Any]]:
        """Returns the complete execution trace log."""
        return list(self._trace_log)

    # ──────────────────────────────────────────────
    #  Risk Tier: Interactive Environment Detection
    # ──────────────────────────────────────────────

    def _is_interactive(self) -> bool:
        """Check if stdin is truly interactive (Defense #5).
        
        Catches broken PTY allocations (SSH -T), systemd services,
        and Kubernetes exec without stdin attached.
        """
        # Allow synthetic testing via env var
        if os.environ.get("TOOLGUARD_OS_PIPE_TEST"):
            return True
        if not sys.stdin.isatty():
            return False
        try:
            # Verify stdin is truly readable
            if hasattr(sys.stdin, 'fileno'):
                os.fstat(sys.stdin.fileno())
            return True
        except (OSError, ValueError, AttributeError):
            return False  # Fail-close

    # ──────────────────────────────────────────────
    #  Risk Tier: Approval Cache (Tier 2 only)
    # ──────────────────────────────────────────────

    def _check_approval_cache(self, tool_name: str) -> bool:
        """Check if a Tier 2 tool has a valid cached approval (Defense #4)."""
        name = tool_name.strip().casefold()
        with self._approval_cache_lock:
            expiry = self._approval_cache.get(name, 0)
            if time.time() < expiry:
                self._log("CACHED_APPROVAL", tool_name, 
                          f"Using cached approval (expires in {int(expiry - time.time())}s)")
                return True
            # Clean expired entry
            self._approval_cache.pop(name, None)
            return False

    def _cache_approval(self, tool_name: str, ttl: int) -> None:
        """Cache a Tier 2 approval for the given TTL in seconds."""
        name = tool_name.strip().casefold()
        with self._approval_cache_lock:
            self._approval_cache[name] = time.time() + ttl
        self._log("CACHE_SET", tool_name, f"Approval cached for {ttl}s")

    def clear_approval_cache(self) -> None:
        """Clear all cached approvals. Call this on policy reload (Defense #7)."""
        with self._approval_cache_lock:
            self._approval_cache.clear()

    # ──────────────────────────────────────────────
    #  Risk Tier 2: Restricted — Human Approval
    # ──────────────────────────────────────────────

    def _request_approval(self, tool_name: str, arguments: dict, 
                          tier: int, timeout: int = 30) -> bool:
        """Request human approval for a Tier 2 (Restricted) tool.
        
        Features:
          - Headless fail-close (Defense #5)
          - Stdin mutex lock (Defense #1)
          - Configurable timeout, auto-deny on expiry
        """
        # 1. Interactive environment check
        if not self._is_interactive():
            print(
                f"\n🛡️  [ToolGuard] HEADLESS ENFORCER\n"
                f"   Terminal unavailable for Risk Tier {tier} execution.\n"
                f"   Auto-denying to prevent deadlock.",
                file=sys.stderr,
            )
            return False

        # 2. Acquire stdin lock (Defense #1: prevent thread race on input())
        with self._stdin_lock:
            try:
                print(
                    f"\n🛡️  [ToolGuard] APPROVAL REQUIRED\n"
                    f"   Tool:      {tool_name}\n"
                    f"   Arguments: {arguments}\n"
                    f"   Risk Tier: {tier} (restricted)\n"
                    f"   Timeout:   {timeout}s\n",
                    file=sys.stderr,
                )

                # 3. Threaded input with configurable timeout
                if timeout <= 0:
                    # Legacy mode: wait forever (timeout=0)
                    response = input("   Approve? [y/N]: ").strip().lower()
                    return response in ("y", "yes")

                result_holder = [None]
                def _ask():
                    try:
                        result_holder[0] = input("   Approve? [y/N]: ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        result_holder[0] = "n"

                ask_thread = threading.Thread(target=_ask, daemon=True)
                ask_thread.start()
                ask_thread.join(timeout=timeout)

                if result_holder[0] is None:
                    print(
                        f"\n   ⏱️  Approval timed out after {timeout}s. Auto-denying.",
                        file=sys.stderr,
                    )
                    return False
                return result_holder[0] in ("y", "yes")

            except (EOFError, KeyboardInterrupt):
                return False

    # ──────────────────────────────────────────────
    #  Risk Tier 3: Critical — Double-Confirm
    # ──────────────────────────────────────────────

    def _request_critical_approval(self, tool_name: str, arguments: dict) -> bool:
        """Request critical double-confirmation for a Tier 3 tool.
        
        The user must type the exact tool name (case-insensitive) to confirm.
        This prevents muscle-memory "y" approvals for catastrophic tools.
        No approval caching. Ignores auto_approve.
        """
        # 1. Interactive environment check
        if not self._is_interactive():
            print(
                f"\n🛡️  [ToolGuard] HEADLESS ENFORCER (CRITICAL)\n"
                f"   Terminal unavailable for Risk Tier 3 execution.\n"
                f"   Auto-denying to prevent deadlock.",
                file=sys.stderr,
            )
            return False

        # 2. Acquire stdin lock
        with self._stdin_lock:
            try:
                print(
                    f"\n🛡️  [ToolGuard] CRITICAL TOOL — DOUBLE CONFIRM REQUIRED\n"
                    f"   Tool:      {tool_name}\n"
                    f"   Arguments: {arguments}\n"
                    f"   Risk Tier: 3 (critical / destructive)\n"
                    f"\n   Type the exact tool name to confirm execution:\n",
                    file=sys.stderr,
                )
                response = input("   > ").strip()
                # Defense #6: casefold both sides
                approved = response.casefold() == tool_name.strip().casefold()
                if not approved:
                    print(
                        f"   ❌ Mismatch. Expected '{tool_name}', got '{response}'. Denying.",
                        file=sys.stderr,
                    )
                return approved

            except (EOFError, KeyboardInterrupt):
                return False

    def _emit_trace(self, tool_name: str, arguments: dict, result: InterceptResult, 
                    latency_ms: float = 0.0) -> None:
        """Write a trace JSON file for the Obsidian Dashboard's SSE file watcher."""
        try:
            trace_dir = Path(".toolguard/mcp_traces")
            trace_dir.mkdir(parents=True, exist_ok=True)

            timestamp_ms = int(time.time() * 1000)
            node_id = hex(abs(hash(f"{tool_name}:{timestamp_ms}")))[2:8]
            filename = f"trace_{timestamp_ms}_{node_id}.json"
            trace_path = trace_dir / filename
            
            trace_data = {
                "tool": tool_name.strip().casefold(),
                "raw_tool": tool_name,
                "arguments": arguments,
                "timestamp": time.time(),
                "latency_ms": round(latency_ms, 3),
                "decision": "ALLOWED" if result.allowed else "BLOCKED",
                "layer": result.layer,
                "reason": result.reason,
            }

            trace_path.write_text(json.dumps(trace_data), encoding="utf-8")
        except Exception:
            pass

    def _log(self, status: str, tool_name: str, detail: str) -> None:
        """Log interceptor decisions to stderr if verbose mode is on."""
        if self.verbose:
            print(
                f"  🛡️  [{status}] {tool_name}: {detail}",
                file=sys.stderr,
            )