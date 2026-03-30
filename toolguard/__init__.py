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

__version__ = "5.1.2"
__author__ = "ToolGuard Contributors"

import typing

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
from toolguard.core.tracer import TraceTracker, TraceLog, ToolGuardTraceMismatchError
from toolguard.storage import ResultStore
from toolguard.alerts import configure_alerts

__all__ = [
    # Decorators & wrappers
    "create_tool",
    "GuardedTool",
    # Golden Traces
    "TraceTracker",
    "TraceLog",
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
    "ToolGuardTraceMismatchError",
    "quick_check",
]

def quick_check(tool: typing.Callable, test_cases: typing.Sequence[str] | None = None, iterations: int = 2) -> "ChainTestReport":
    """⚡ Minimal zero-config test for a single tool.
    
    Instantly runs a tool against the fuzzer and prints a Rich report
    to the console. This is the fastest way to test a tool in a Jupyter Notebook.
    
    Returns:
        ChainTestReport with detailed results for programmatic inspection.
    """
    from toolguard.reporters.console import print_chain_report
    report = test_chain([tool], test_cases=test_cases, iterations=iterations, assert_reliability=0.0)
    print_chain_report(report)
    return report
