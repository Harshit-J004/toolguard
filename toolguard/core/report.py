"""
toolguard.core.report
~~~~~~~~~~~~~~~~~~~~~

Test reporting — structured results from chain test runs,
with detailed failure analysis and actionable suggestions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────
#  Step Result — one tool in the chain
# ──────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Result from executing a single step in a tool chain."""

    step: int
    tool_name: str
    success: bool
    input_data: Any = None
    output_data: Any = None
    error: str | None = None
    error_type: str | None = None
    latency_ms: float = 0.0
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool_name": self.tool_name,
            "success": self.success,
            "error": self.error,
            "error_type": self.error_type,
            "latency_ms": round(self.latency_ms, 2),
            "correlation_id": self.correlation_id,
        }


# ──────────────────────────────────────────────────────────
#  Chain Run — one complete chain execution
# ──────────────────────────────────────────────────────────

@dataclass
class ChainRun:
    """Result from running an entire tool chain once."""

    success: bool
    steps: list[StepResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    test_case_type: str = "happy_path"
    correlation_id: str = ""

    @property
    def failed_step(self) -> StepResult | None:
        """Return the first step that failed, if any."""
        for step in self.steps:
            if not step.success:
                return step
        return None

    @property
    def cascade_path(self) -> list[str]:
        """Build a visual cascade path: tool_a ✓ → tool_b ✗ → tool_c ⊘"""
        parts = []
        for step in self.steps:
            if step.success:
                parts.append(f"{step.tool_name} ✓")
            else:
                parts.append(f"{step.tool_name} ✗")
                break
        # Remaining tools that never ran
        tools_run = len(self.steps)
        return parts

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "test_case": self.test_case_type,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "steps": [s.to_dict() for s in self.steps],
            "correlation_id": self.correlation_id,
        }


# ──────────────────────────────────────────────────────────
#  Failure Analysis
# ──────────────────────────────────────────────────────────

@dataclass
class FailureAnalysis:
    """Detailed analysis of a single chain failure."""

    step: int
    tool_name: str
    error_type: str
    error_message: str
    cascade_path: list[str]
    root_cause: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool_name": self.tool_name,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "cascade_path": self.cascade_path,
            "root_cause": self.root_cause,
            "suggestion": self.suggestion,
        }


# ──────────────────────────────────────────────────────────
#  Chain Test Report
# ──────────────────────────────────────────────────────────

class ChainTestReport:
    """Complete report from a chain test run.

    Contains pass/fail stats, reliability %, top failure analyses,
    and rendering methods for console/JSON/HTML.
    """

    def __init__(
        self,
        chain_name: str,
        runs: list[ChainRun],
        tool_names: list[str],
        reliability_threshold: float = 0.95,
    ) -> None:
        self.chain_name = chain_name
        self.runs = runs
        self.tool_names = tool_names
        self.reliability_threshold = reliability_threshold

        # Computed stats
        self.total_tests = len(runs)
        self.passed = sum(1 for r in runs if r.success)
        self.failed = self.total_tests - self.passed
        self.reliability = self.passed / self.total_tests if self.total_tests else 0.0

        # Failure analytics
        self.failure_analyses = self._analyze_failures()
        self.passed_threshold = self.reliability >= reliability_threshold

    # ── Failure analysis engine ──────────────────────────

    def _analyze_failures(self) -> list[FailureAnalysis]:
        """Analyze each failure to extract root cause and suggestions."""
        analyses: list[FailureAnalysis] = []

        for run in self.runs:
            if run.success:
                continue

            failed = run.failed_step
            if not failed:
                continue

            # Determine root cause and suggestion
            root_cause = self._infer_root_cause(failed)
            suggestion = self._infer_suggestion(failed)

            analyses.append(
                FailureAnalysis(
                    step=failed.step,
                    tool_name=failed.tool_name,
                    error_type=failed.error_type or "Unknown",
                    error_message=failed.error or "No error message",
                    cascade_path=run.cascade_path,
                    root_cause=root_cause,
                    suggestion=suggestion,
                )
            )

        return analyses

    def _infer_root_cause(self, step: StepResult) -> str:
        """Infer the root cause from the error type and context."""
        err = (step.error or "").lower()
        etype = (step.error_type or "").lower()

        if "none" in err or "null" in err or "nonetype" in err:
            return f"{step.tool_name} received or returned null/None value"
        if "key" in err and "error" in etype:
            return f"{step.tool_name} tried to access a missing key in input data"
        if "type" in err and "error" in etype:
            return f"{step.tool_name} received wrong data type (type mismatch in chain)"
        if "timeout" in err or "timed out" in err:
            return f"{step.tool_name} timed out (upstream service too slow)"
        if "validation" in err:
            return f"{step.tool_name} input/output failed schema validation"
        if "connection" in err:
            return f"{step.tool_name} couldn't connect to upstream service"
        return f"{step.tool_name} failed with: {step.error_type or 'unknown error'}"

    def _infer_suggestion(self, step: StepResult) -> str:
        """Generate an actionable suggestion for the failure."""
        err = (step.error or "").lower()

        if "none" in err or "null" in err:
            return f"Add null check: if data is None: return default_value(). Or add a default in {step.tool_name}'s output schema."
        if "key" in err:
            return f"Use data.get('key', default) instead of data['key'] in {step.tool_name}. Or validate upstream tool output includes required fields."
        if "type" in err:
            return f"Check type compatibility between tools. The previous tool may return str where {step.tool_name} expects int."
        if "timeout" in err:
            return f"Increase timeout for {step.tool_name} or add @with_retry() for transient failures."
        if "validation" in err:
            return f"Review the schema for {step.tool_name}. Input data doesn't match expected Pydantic model."
        return f"Review {step.tool_name}'s error handling. Consider wrapping with @with_retry() or adding input validation."

    # ── Top failures (grouped) ───────────────────────────

    @property
    def top_failures(self) -> list[dict[str, Any]]:
        """Group failures by tool_name + error_type, sorted by frequency."""
        counter: dict[str, int] = {}
        for fa in self.failure_analyses:
            key = f"{fa.tool_name}|{fa.error_type}"
            counter[key] = counter.get(key, 0) + 1

        grouped = []
        seen: set[str] = set()
        for fa in self.failure_analyses:
            key = f"{fa.tool_name}|{fa.error_type}"
            if key not in seen:
                seen.add(key)
                grouped.append({
                    "tool_name": fa.tool_name,
                    "error_type": fa.error_type,
                    "count": counter[key],
                    "root_cause": fa.root_cause,
                    "suggestion": fa.suggestion,
                })

        return sorted(grouped, key=lambda x: x["count"], reverse=True)

    # ── Serialisation ────────────────────────────────────

    def summary(self) -> str:
        """Human-readable text summary."""
        lines = [
            f"Chain Test Report: {self.chain_name}",
            f"{'═' * 50}",
            f"  ✓ {self.passed} passed",
            f"  ✗ {self.failed} failed",
            f"  📊 {self.reliability:.1%} reliability (threshold: {self.reliability_threshold:.0%})",
            "",
        ]

        if self.failure_analyses:
            lines.append("Top Failures:")
            for i, tf in enumerate(self.top_failures[:5], 1):
                lines.append(f"  {i}. [{tf['count']}x] {tf['tool_name']} → {tf['error_type']}")
                lines.append(f"     Root cause: {tf['root_cause']}")
                lines.append(f"     💡 {tf['suggestion']}")
                lines.append("")

        status = "✅ PASSED" if self.passed_threshold else "❌ BELOW THRESHOLD"
        lines.append(f"Result: {status}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_name": self.chain_name,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "reliability": self.reliability,
            "reliability_threshold": self.reliability_threshold,
            "passed_threshold": self.passed_threshold,
            "tool_names": self.tool_names,
            "top_failures": self.top_failures,
            "runs": [r.to_dict() for r in self.runs],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
