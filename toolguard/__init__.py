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
from toolguard.core.validator import create_tool, GuardedTool
from toolguard.core.chain import test_chain, ChainRunner
from toolguard.core.schema import ToolSchema
from toolguard.core.report import ChainTestReport
from toolguard.core.retry import RetryPolicy, CircuitBreaker, with_retry, with_circuit_breaker
from toolguard.core.errors import (
    ToolGuardError,
    SchemaValidationError,
    ChainExecutionError,
    ToolTimeoutError,
    CircuitBreakerOpenError,
    CompatibilityError,
)
from toolguard.core.scoring import (
    score_chain,
    ReliabilityScore,
    RiskLevel,
    DeployRecommendation,
)
from toolguard.storage import ResultStore

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
