"""
toolguard.core.retry
~~~~~~~~~~~~~~~~~~~~

Resilience patterns for tool execution:
  - RetryPolicy   — exponential backoff with jitter
  - CircuitBreaker — fail-fast when a tool is consistently broken

These can be composed with @create_tool for production-grade reliability.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

from toolguard.core.errors import CircuitBreakerOpenError

# ──────────────────────────────────────────────────────────
#  Retry Policy
# ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behavior.

    Attributes:
        max_retries:          Maximum number of retry attempts.
        backoff_base:         Base delay in seconds for exponential backoff.
        backoff_max:          Maximum delay cap in seconds.
        jitter:               Whether to add random jitter to prevent thundering herd.
        retryable_exceptions: Exception types that should trigger a retry.
    """

    max_retries: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    )


def _compute_delay(attempt: int, policy: RetryPolicy) -> float:
    """Compute backoff delay for a given attempt number."""
    delay = min(policy.backoff_base * (2 ** attempt), policy.backoff_max)
    if policy.jitter:
        delay *= random.uniform(0.5, 1.5)
    return delay


def with_retry(policy: RetryPolicy | None = None) -> Callable:
    """Decorator that adds retry logic with exponential backoff.

    Usage:
        @with_retry(RetryPolicy(max_retries=3))
        def call_api(data: dict) -> dict:
            return requests.post(...).json()
    """
    policy = policy or RetryPolicy()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(policy.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except policy.retryable_exceptions as exc:
                    last_exception = exc
                    if attempt < policy.max_retries:
                        delay = _compute_delay(attempt, policy)
                        time.sleep(delay)
                    # Non-retryable exceptions propagate immediately

            raise last_exception  # type: ignore[misc]

        wrapper._retry_policy = policy  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ──────────────────────────────────────────────────────────
#  Circuit Breaker
# ──────────────────────────────────────────────────────────

class CircuitState(str, Enum):
    """States of the circuit breaker."""
    CLOSED = "CLOSED"        # Normal — requests flow through
    OPEN = "OPEN"            # Tripped — requests are rejected
    HALF_OPEN = "HALF_OPEN"  # Testing — one request allowed to probe


class CircuitBreaker:
    """Circuit breaker pattern for tool calls.

    When a tool fails too often, the breaker trips OPEN and rejects
    all calls for `reset_timeout` seconds.  After that, it moves to
    HALF_OPEN and lets one call through as a probe.  On success,
    it resets to CLOSED; on failure, it goes back to OPEN.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60.0)

        @with_circuit_breaker(breaker)
        def call_flaky_api(data: dict) -> dict:
            ...
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        tool_name: str = "",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.tool_name = tool_name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    # ── Public properties ────────────────────────────────

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # ── State transitions ────────────────────────────────

    def record_success(self) -> None:
        """Record a successful call → reset to CLOSED."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call → potentially trip to OPEN."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current = self.state  # triggers OPEN → HALF_OPEN check
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # allow one probe
        return False

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def summary(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
        }


def with_circuit_breaker(breaker: CircuitBreaker) -> Callable:
    """Decorator that guards a function with a circuit breaker.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5)

        @with_circuit_breaker(breaker)
        def call_api(data: dict) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = breaker.tool_name or getattr(func, "__name__", "unknown")

            if not breaker.allow_request():
                raise CircuitBreakerOpenError(
                    tool_name=tool_name,
                    failure_count=breaker.failure_count,
                    threshold=breaker.failure_threshold,
                    reset_timeout=breaker.reset_timeout,
                )

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception:
                breaker.record_failure()
                raise

        wrapper._circuit_breaker = breaker  # type: ignore[attr-defined]
        return wrapper

    return decorator
