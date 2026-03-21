"""
toolguard.core.errors
~~~~~~~~~~~~~~~~~~~~~

Standardized exception hierarchy for ToolGuard.

Every error carries rich context: tool name, step number, correlation ID,
and an actionable suggestion so developers know exactly what to fix.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_correlation_id() -> str:
    """Generate a short, human-readable correlation ID."""
    return uuid.uuid4().hex[:12]


# ──────────────────────────────────────────────────────────
#  Base Exception
# ──────────────────────────────────────────────────────────

class ToolGuardError(Exception):
    """Base exception for all ToolGuard errors.

    Attributes:
        message:        Human-readable description of the error.
        tool_name:      Name of the tool that raised the error.
        correlation_id: Unique ID to trace this error across a chain.
        suggestion:     Actionable fix suggestion for the developer.
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        correlation_id: str | None = None,
        suggestion: str = "",
    ) -> None:
        self.tool_name = tool_name
        self.correlation_id = correlation_id or _new_correlation_id()
        self.suggestion = suggestion
        super().__init__(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.tool_name:
            parts.append(f"  Tool: {self.tool_name}")
        if self.suggestion:
            parts.append(f"  💡 Suggestion: {self.suggestion}")
        parts.append(f"  Correlation ID: {self.correlation_id}")
        return "\n".join(parts)


# ──────────────────────────────────────────────────────────
#  Schema & Validation Errors
# ──────────────────────────────────────────────────────────

class SchemaValidationError(ToolGuardError):
    """Raised when tool input or output fails Pydantic validation.

    Carries the raw validation errors so reporters can render
    field-level detail.
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        direction: str = "input",  # "input" or "output"
        validation_errors: list[dict[str, Any]] | None = None,
        correlation_id: str | None = None,
        suggestion: str = "",
    ) -> None:
        self.direction = direction
        self.validation_errors = validation_errors or []
        super().__init__(
            message,
            tool_name=tool_name,
            correlation_id=correlation_id,
            suggestion=suggestion or f"Check the {direction} schema for {tool_name}.",
        )


# ──────────────────────────────────────────────────────────
#  Approval & Security Errors
# ──────────────────────────────────────────────────────────

class ToolGuardApprovalDeniedError(ToolGuardError):
    """Raised when a human-in-the-loop rejects a Tier 2+ tool execution."""

    def __init__(
        self,
        message: str = "Execution blocked by human-in-the-loop approval.",
        *,
        tool_name: str = "",
        risk_tier: int = 0,
        correlation_id: str | None = None,
    ) -> None:
        self.risk_tier = risk_tier
        super().__init__(
            message,
            tool_name=tool_name,
            correlation_id=correlation_id,
            suggestion=f"Tool '{tool_name}' requires Tier {risk_tier} interactive approval.",
        )


class ToolGuardTraceMismatchError(ToolGuardError):
    """Raised when an agent's execution path deviates from the Golden Trace."""

    def __init__(
        self,
        message: str = "Execution path deviated from Golden Trace.",
        *,
        expected_path: list[str] | None = None,
        actual_path: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.expected_path = expected_path or []
        self.actual_path = actual_path or []
        super().__init__(
            message,
            tool_name="TraceTracker",
            correlation_id=correlation_id,
            suggestion=f"Agent called {self.actual_path} but you asserted {self.expected_path}.",
        )


# ──────────────────────────────────────────────────────────
#  Chain Execution Errors
# ──────────────────────────────────────────────────────────

class ChainExecutionError(ToolGuardError):
    """Raised when a tool chain fails during execution.

    Captures the step index and the cascade path so the reporter
    can visualize exactly where things went wrong.
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        step: int = 0,
        total_steps: int = 0,
        cascade_path: list[str] | None = None,
        correlation_id: str | None = None,
        suggestion: str = "",
    ) -> None:
        self.step = step
        self.total_steps = total_steps
        self.cascade_path = cascade_path or []
        super().__init__(
            message,
            tool_name=tool_name,
            correlation_id=correlation_id,
            suggestion=suggestion,
        )

    def __str__(self) -> str:
        base = super().__str__()
        cascade = " → ".join(self.cascade_path) if self.cascade_path else "N/A"
        return f"{base}\n  Step: {self.step}/{self.total_steps}\n  Cascade: {cascade}"


# ──────────────────────────────────────────────────────────
#  Timeout & Resilience Errors
# ──────────────────────────────────────────────────────────

class ToolTimeoutError(ToolGuardError):
    """Raised when a tool exceeds its configured timeout."""

    def __init__(
        self,
        message: str = "Tool execution timed out.",
        *,
        tool_name: str = "",
        timeout_seconds: float = 0.0,
        correlation_id: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(
            message,
            tool_name=tool_name,
            correlation_id=correlation_id,
            suggestion=f"Increase timeout (currently {timeout_seconds}s) or optimize {tool_name}.",
        )


class CircuitBreakerOpenError(ToolGuardError):
    """Raised when a circuit breaker is open and rejects the call."""

    def __init__(
        self,
        message: str = "Circuit breaker is OPEN — tool calls are being rejected.",
        *,
        tool_name: str = "",
        failure_count: int = 0,
        threshold: int = 0,
        reset_timeout: float = 0.0,
        correlation_id: str | None = None,
    ) -> None:
        self.failure_count = failure_count
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        super().__init__(
            message,
            tool_name=tool_name,
            correlation_id=correlation_id,
            suggestion=(
                f"{tool_name} failed {failure_count}/{threshold} times. "
                f"Circuit resets in {reset_timeout:.0f}s. Check upstream service health."
            ),
        )


# ──────────────────────────────────────────────────────────
#  Compatibility Errors
# ──────────────────────────────────────────────────────────

class CompatibilityError(ToolGuardError):
    """Raised when tools in a chain have incompatible schemas."""

    def __init__(
        self,
        message: str,
        *,
        source_tool: str = "",
        target_tool: str = "",
        conflicts: list[str] | None = None,
        correlation_id: str | None = None,
        suggestion: str = "",
    ) -> None:
        self.source_tool = source_tool
        self.target_tool = target_tool
        self.conflicts = conflicts or []
        super().__init__(
            message,
            tool_name=f"{source_tool} → {target_tool}",
            correlation_id=correlation_id,
            suggestion=suggestion,
        )


# ──────────────────────────────────────────────────────────
#  Error Context Builder  (used internally by chain runner)
# ──────────────────────────────────────────────────────────

@dataclass
class ErrorContext:
    """Structured context attached to every failure in a chain run."""

    tool_name: str = ""
    step: int = 0
    correlation_id: str = field(default_factory=_new_correlation_id)
    input_snapshot: Any = None
    output_snapshot: Any = None
    error_type: str = ""
    error_message: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "step": self.step,
            "correlation_id": self.correlation_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "suggestion": self.suggestion,
        }
