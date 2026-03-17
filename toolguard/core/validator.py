"""
toolguard.core.validator
~~~~~~~~~~~~~~~~~~~~~~~~

The @create_tool decorator — the heart of ToolGuard.

Wraps any function with automatic Pydantic input/output validation,
execution stats tracking, and OpenTelemetry span emission.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from toolguard.core.errors import SchemaValidationError, _new_correlation_id
from toolguard.core.schema import ToolSchema, auto_generate_input_model, auto_generate_schema

# ──────────────────────────────────────────────────────────
#  Execution Stats (thread-safe)
# ──────────────────────────────────────────────────────────

@dataclass
class ToolStats:
    """Tracks runtime statistics for a guarded tool."""

    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_calls if self.total_calls else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_calls if self.total_calls else 0.0

    def record_success(self, latency_ms: float) -> None:
        with self._lock:
            self.total_calls += 1
            self.success_count += 1
            self.total_latency_ms += latency_ms

    def record_failure(self, latency_ms: float) -> None:
        with self._lock:
            self.total_calls += 1
            self.failure_count += 1
            self.total_latency_ms += latency_ms

    def summary(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "success_rate": f"{self.success_rate:.1%}",
            "avg_latency_ms": f"{self.avg_latency_ms:.1f}",
            "failures": self.failure_count,
        }


# ──────────────────────────────────────────────────────────
#  GuardedTool — the wrapper object
# ──────────────────────────────────────────────────────────

class GuardedTool:
    """A tool function wrapped with ToolGuard validation.

    This is what @create_tool returns.  It's callable (behaves like
    the original function) but also exposes:
        .schema    — ToolSchema metadata
        .stats     — Runtime ToolStats
        .unwrap()  — Returns the original unwrapped function
    """

    def __init__(
        self,
        func: Callable,
        *,
        input_model: type[BaseModel] | None = None,
        output_model: type[BaseModel] | None = None,
        schema: ToolSchema | None = None,
    ) -> None:
        self._func = func
        self._input_model = input_model
        self._output_model = output_model
        self._sig = inspect.signature(func)
        self._is_async = asyncio.iscoroutinefunction(func)
        self.stats = ToolStats()

        # Build schema
        self.schema = schema or auto_generate_schema(func, output_model=output_model)

        # Preserve function identity
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self.__module__ = getattr(func, "__module__", "")
        self.__qualname__ = getattr(func, "__qualname__", func.__name__)
        self._toolguard_wrapped = True

    # ── Core call path ───────────────────────────────────

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the guarded tool. Handles both sync and async functions.

        If the wrapped function is async, returns a coroutine that
        the caller must `await`. If sync, returns the result directly.
        This makes GuardedTool a transparent drop-in wrapper.
        """
        if self._is_async:
            return self._acall(*args, **kwargs)
        return self._sync_call(*args, **kwargs)

    def _sync_call(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous execution path (original behaviour, unchanged)."""
        correlation_id = _new_correlation_id()
        start = time.perf_counter()

        try:
            # 1. Validate inputs
            validated_kwargs = self._validate_input(*args, **kwargs, _correlation_id=correlation_id)

            # 2. Execute the tool
            result = self._func(**validated_kwargs)

            # 3. Validate output
            result = self._validate_output(result, _correlation_id=correlation_id)

            # 4. Record success
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_success(latency)

            return result

        except SchemaValidationError:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

        except Exception:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

    async def _acall(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous execution path for async def tools."""
        correlation_id = _new_correlation_id()
        start = time.perf_counter()

        try:
            # 1. Validate inputs (always synchronous — Pydantic is sync)
            validated_kwargs = self._validate_input(*args, **kwargs, _correlation_id=correlation_id)

            # 2. Execute the async tool
            result = await self._func(**validated_kwargs)

            # 3. Validate output (always synchronous)
            result = self._validate_output(result, _correlation_id=correlation_id)

            # 4. Record success
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_success(latency)

            return result

        except SchemaValidationError:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

        except Exception:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

    # ── Validation logic ─────────────────────────────────

    def _validate_input(
        self, *args: Any, _correlation_id: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        """Bind positional + keyword args, validate against input model."""
        if not self._input_model:
            # No model → just bind args to keyword dict
            bound = self._sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return dict(bound.arguments)

        try:
            bound = self._sig.bind(*args, **kwargs)
            bound.apply_defaults()
            validated = self._input_model(**bound.arguments)
            return validated.model_dump()
        except ValidationError as e:
            raise SchemaValidationError(
                f"Input validation failed for '{self.__name__}'",
                tool_name=self.__name__,
                direction="input",
                validation_errors=e.errors(),
                correlation_id=_correlation_id,
                suggestion=(
                    f"Check the arguments passed to {self.__name__}(). "
                    f"Expected schema: {self._input_model.model_json_schema()}"
                ),
            ) from e

    def _validate_output(self, result: Any, *, _correlation_id: str = "") -> Any:
        """Validate the tool's return value against the output model."""
        if not self._output_model:
            return result

        try:
            if isinstance(result, dict):
                validated = self._output_model(**result)
            else:
                validated = self._output_model(value=result)
            return validated.model_dump()
        except ValidationError as e:
            raise SchemaValidationError(
                f"Output validation failed for '{self.__name__}'",
                tool_name=self.__name__,
                direction="output",
                validation_errors=e.errors(),
                correlation_id=_correlation_id,
                suggestion=(
                    f"{self.__name__} returned data that doesn't match the expected schema. "
                    f"Got: {type(result).__name__}. "
                    f"Expected: {self._output_model.model_json_schema()}"
                ),
            ) from e

    # ── Utilities ────────────────────────────────────────

    def unwrap(self) -> Callable:
        """Get the original, unwrapped function."""
        return self._func

    def __repr__(self) -> str:
        return f"<GuardedTool {self.__name__} | calls={self.stats.total_calls} | success={self.stats.success_rate:.0%}>"


# ──────────────────────────────────────────────────────────
#  @create_tool decorator
# ──────────────────────────────────────────────────────────

def create_tool(
    schema: str | dict[str, Any] = "auto",
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
    version: str = "1.0.0",
) -> Callable[[Callable], GuardedTool]:
    """Decorator that wraps a function with ToolGuard validation.

    Usage:
        @create_tool(schema="auto")
        def get_weather(location: str, units: str = "metric") -> dict:
            return {"temp": 22.5, "units": units}

        @create_tool(output_model=WeatherOutput)
        def get_weather(location: str) -> dict:
            ...

    Args:
        schema:       "auto" to generate from type hints, or a dict schema.
        input_model:  Explicit Pydantic model for inputs.
        output_model: Explicit Pydantic model for outputs.
        version:      Tool version string.
    """

    def decorator(func: Callable) -> GuardedTool:
        # Resolve input model
        resolved_input = input_model
        if resolved_input is None and schema == "auto":
            resolved_input = auto_generate_input_model(func)

        # Build schema
        tool_schema = auto_generate_schema(func, output_model=output_model)
        tool_schema.version = version

        return GuardedTool(
            func,
            input_model=resolved_input,
            output_model=output_model,
            schema=tool_schema,
        )

    return decorator
