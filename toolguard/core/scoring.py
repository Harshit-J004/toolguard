"""
toolguard.core.scoring
~~~~~~~~~~~~~~~~~~~~~~

Reliability scoring engine — quantifies trust in a tool chain.

Produces a ReliabilityScore with:
  - Overall reliability percentage
  - Risk level (CRITICAL / HIGH / MEDIUM / LOW / SAFE)
  - Failure distribution by category
  - Per-tool breakdown
  - Deployment recommendation (BLOCK / WARN / PASS)

This becomes the "deploy gate" feature:
    score = score_chain(report)
    if score.deploy_recommendation == "BLOCK":
        sys.exit(1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING
from collections import Counter

if TYPE_CHECKING:
    from toolguard.core.report import ChainTestReport


# ──────────────────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    """Risk classification for a tool chain."""
    CRITICAL = "CRITICAL"  # < 50% reliability
    HIGH = "HIGH"          # 50-70%
    MEDIUM = "MEDIUM"      # 70-85%
    LOW = "LOW"            # 85-95%
    SAFE = "SAFE"          # > 95%


class DeployRecommendation(str, Enum):
    """Whether this chain should be deployed."""
    BLOCK = "BLOCK"  # Do NOT deploy
    WARN = "WARN"    # Deploy with caution
    PASS = "PASS"    # Safe to deploy


# ──────────────────────────────────────────────────────────
#  Failure Category
# ──────────────────────────────────────────────────────────

class FailureCategory(str, Enum):
    """Categories of tool chain failures."""
    NULL_PROPAGATION = "null_propagation"
    TYPE_MISMATCH = "type_mismatch"
    MISSING_FIELD = "missing_field"
    SCHEMA_VIOLATION = "schema_violation"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


def _categorize_failure(error: str, error_type: str) -> FailureCategory:
    """Classify a failure into a category based on error content."""
    err = (error or "").lower()
    etype = (error_type or "").lower()

    if "none" in err or "null" in err or "nonetype" in err:
        return FailureCategory.NULL_PROPAGATION
    if "type" in etype and "error" in etype:
        return FailureCategory.TYPE_MISMATCH
    if "key" in err and "error" in etype:
        return FailureCategory.MISSING_FIELD
    if "validation" in err or "schema" in err:
        return FailureCategory.SCHEMA_VIOLATION
    if "timeout" in err or "timed out" in err:
        return FailureCategory.TIMEOUT
    if "connection" in err:
        return FailureCategory.CONNECTION
    return FailureCategory.UNKNOWN


# ──────────────────────────────────────────────────────────
#  Per-Tool Score
# ──────────────────────────────────────────────────────────

@dataclass
class ToolScore:
    """Reliability score for a single tool in the chain."""
    name: str
    total_executions: int = 0
    failures: int = 0
    failure_categories: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 1.0
        return (self.total_executions - self.failures) / self.total_executions

    @property
    def is_bottleneck(self) -> bool:
        """A tool is a bottleneck if it fails > 20% of the time."""
        return self.success_rate < 0.80

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "success_rate": f"{self.success_rate:.1%}",
            "failures": self.failures,
            "total": self.total_executions,
            "is_bottleneck": self.is_bottleneck,
            "failure_categories": self.failure_categories,
        }


# ──────────────────────────────────────────────────────────
#  Reliability Score (the main output)
# ──────────────────────────────────────────────────────────

@dataclass
class ReliabilityScore:
    """Complete reliability assessment for a tool chain.

    This is what developers see in CLI output and CI/CD gates.
    """
    chain_name: str
    reliability: float
    risk_level: RiskLevel
    deploy_recommendation: DeployRecommendation
    total_runs: int
    passed: int
    failed: int
    failure_distribution: dict[str, int]
    tool_scores: list[ToolScore]
    top_risk: str  # Human-readable top risk description
    confidence: float  # Statistical confidence (higher = more data)

    def summary(self) -> str:
        """Human-readable summary for CLI output."""
        risk_icons = {
            RiskLevel.CRITICAL: "🔴",
            RiskLevel.HIGH: "🟠",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.LOW: "🟢",
            RiskLevel.SAFE: "✅",
        }
        deploy_icons = {
            DeployRecommendation.BLOCK: "🚫 BLOCK",
            DeployRecommendation.WARN: "⚠️  WARN",
            DeployRecommendation.PASS: "✅ PASS",
        }

        lines = [
            f"╔══════════════════════════════════════════════════╗",
            f"║  Reliability Score: {self.chain_name:<29}║",
            f"╠══════════════════════════════════════════════════╣",
            f"║  Score:      {self.reliability:>6.1%}                             ║",
            f"║  Risk Level: {risk_icons[self.risk_level]} {self.risk_level.value:<10}                    ║",
            f"║  Deploy:     {deploy_icons[self.deploy_recommendation]:<15}                   ║",
            f"║  Confidence: {self.confidence:>6.1%}                             ║",
            f"╠══════════════════════════════════════════════════╣",
        ]

        # Top risk
        if self.top_risk:
            lines.append(f"║  ⚠️  Top Risk: {self.top_risk:<33}║")
            lines.append(f"╠══════════════════════════════════════════════════╣")

        # Failure distribution
        if self.failure_distribution:
            lines.append(f"║  Failure Distribution:                           ║")
            for category, count in sorted(
                self.failure_distribution.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                pct = count / self.failed * 100 if self.failed > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"║    {category:<18} {bar} {count:>3} ({pct:.0f}%)  ║")
            lines.append(f"╠══════════════════════════════════════════════════╣")

        # Bottleneck tools
        bottlenecks = [t for t in self.tool_scores if t.is_bottleneck]
        if bottlenecks:
            lines.append(f"║  ⚠️  Bottleneck Tools:                            ║")
            for tool in bottlenecks:
                lines.append(f"║    → {tool.name:<20} ({tool.success_rate:.0%} success)    ║")
            lines.append(f"╠══════════════════════════════════════════════════╣")

        lines.append(f"╚══════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_name": self.chain_name,
            "reliability": self.reliability,
            "risk_level": self.risk_level.value,
            "deploy_recommendation": self.deploy_recommendation.value,
            "confidence": self.confidence,
            "total_runs": self.total_runs,
            "passed": self.passed,
            "failed": self.failed,
            "top_risk": self.top_risk,
            "failure_distribution": self.failure_distribution,
            "tool_scores": [t.to_dict() for t in self.tool_scores],
        }


# ──────────────────────────────────────────────────────────
#  Scoring Engine
# ──────────────────────────────────────────────────────────

def _compute_risk_level(reliability: float) -> RiskLevel:
    """Map reliability percentage to risk level."""
    if reliability < 0.50:
        return RiskLevel.CRITICAL
    elif reliability < 0.70:
        return RiskLevel.HIGH
    elif reliability < 0.85:
        return RiskLevel.MEDIUM
    elif reliability < 0.95:
        return RiskLevel.LOW
    else:
        return RiskLevel.SAFE


def _compute_deploy_recommendation(
    risk: RiskLevel,
    reliability: float,
    threshold: float,
) -> DeployRecommendation:
    """Determine deployment recommendation."""
    if risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        return DeployRecommendation.BLOCK
    if reliability < threshold:
        return DeployRecommendation.WARN
    return DeployRecommendation.PASS


def _compute_confidence(total_runs: int) -> float:
    """Statistical confidence based on sample size.

    More test runs → higher confidence in the score.
    We use a simple sigmoid-like curve:
      10 runs = ~50% confidence
      50 runs = ~90% confidence
      100+ runs = ~98% confidence
    """
    import math
    return 1.0 - math.exp(-0.05 * total_runs)


def score_chain(report: ChainTestReport) -> ReliabilityScore:
    """Score a chain test report and produce a ReliabilityScore.

    This is the main entry point for the scoring engine.

    Args:
        report: A ChainTestReport from test_chain().

    Returns:
        ReliabilityScore with full assessment.
    """
    # Failure distribution
    failure_counts: Counter[str] = Counter()
    tool_failures: dict[str, ToolScore] = {}

    # Initialize tool scores
    for name in report.tool_names:
        tool_failures[name] = ToolScore(name=name)

    # Analyze each run
    for run in report.runs:
        # Count executions for each tool that ran
        for step in run.steps:
            ts = tool_failures[step.tool_name]
            ts.total_executions += 1

            if not step.success:
                ts.failures += 1
                category = _categorize_failure(
                    step.error or "",
                    step.error_type or "",
                )
                failure_counts[category.value] += 1

                # Track per-tool categories
                cat_name = category.value
                ts.failure_categories[cat_name] = ts.failure_categories.get(cat_name, 0) + 1

    # Compute scores
    risk = _compute_risk_level(report.reliability)
    deploy = _compute_deploy_recommendation(
        risk, report.reliability, report.reliability_threshold,
    )
    confidence = _compute_confidence(report.total_tests)

    # Determine top risk
    top_risk = ""
    if failure_counts:
        top_category = failure_counts.most_common(1)[0]
        category_descriptions = {
            "null_propagation": "Null values propagating through chain",
            "type_mismatch": "Type mismatches between tools",
            "missing_field": "Missing required fields in tool output",
            "schema_violation": "Schema validation failures",
            "timeout": "Tool execution timeouts",
            "connection": "Connection failures to upstream services",
            "unknown": "Unclassified errors",
        }
        top_risk = category_descriptions.get(
            top_category[0],
            f"{top_category[0]} ({top_category[1]} occurrences)",
        )

    return ReliabilityScore(
        chain_name=report.chain_name,
        reliability=report.reliability,
        risk_level=risk,
        deploy_recommendation=deploy,
        total_runs=report.total_tests,
        passed=report.passed,
        failed=report.failed,
        failure_distribution=dict(failure_counts),
        tool_scores=list(tool_failures.values()),
        top_risk=top_risk,
        confidence=confidence,
    )
