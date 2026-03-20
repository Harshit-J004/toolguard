"""
ToolGuard — Reliability testing for AI agent tool chains.

Catch cascading failures before production. Make agent tool calling
as predictable as unit tests made software reliable.

Usage:
    from toolguard import create_tool, test_chain, GuardedTool

    @create_tool(schema="auto")
    def get_weather(location: str) -> dict:
        ...

    report = test_chain([get_weather, process, alert], assert_reliability=0.95)
"""

__version__ = "0.1.0"
__author__ = "ToolGuard Contributors"

# Core API — the public surface that users import
from toolguard.core.chain import ChainRunner, test_chain
from toolguard.core.errors import (
    ChainExecutionError,
    CircuitBreakerOpenError,
    CompatibilityError,
    SchemaValidationError,
    ToolGuardError,
    ToolTimeoutError,
)
from toolguard.core.report import ChainTestReport
from toolguard.core.retry import CircuitBreaker, RetryPolicy, with_circuit_breaker, with_retry
from toolguard.core.schema import ToolSchema
from toolguard.core.scoring import (
    DeployRecommendation,
    ReliabilityScore,
    RiskLevel,
    score_chain,
)
from toolguard.core.validator import GuardedTool, create_tool
from toolguard.storage import ResultStore
from toolguard.alerts import configure_alerts

__all__ = [
    # Decorators & wrappers
    "create_tool",
    "GuardedTool",
    # Chain testing
    "test_chain",
    "ChainRunner",
    "ChainTestReport",
    # Schema
    "ToolSchema",
    # Resilience
    "RetryPolicy",
    "CircuitBreaker",
    "with_retry",
    "with_circuit_breaker",
    # Scoring
    "score_chain",
    "ReliabilityScore",
    "RiskLevel",
    "DeployRecommendation",
    # Storage
    "ResultStore",
    # Errors
    "ToolGuardError",
    "SchemaValidationError",
    "ChainExecutionError",
    "ToolTimeoutError",
    "CircuitBreakerOpenError",
    "CompatibilityError",
]
