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

import os
from toolguard.core.errors import SchemaValidationError, ToolGuardApprovalDeniedError, _new_correlation_id
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
        risk_tier: int = 0,
    ) -> None:
        self._func = func
        self.risk_tier = risk_tier
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

    @property
    def name(self) -> str:
        return self.__name__

    @name.setter
    def name(self, val: str) -> None:
        self.__name__ = val

    @property
    def description(self) -> str:
        return self.__doc__ or ""

    @description.setter
    def description(self, val: str) -> None:
        self.__doc__ = val

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

            # 2. Human-In-The-Loop Security Check
            if getattr(self, "risk_tier", 0) >= 2 and os.environ.get("TOOLGUARD_AUTO_APPROVE") != "1":
                from rich.prompt import Confirm
                from rich.console import Console
                Console().print(f"\n[bold red]⚠️  SECURITY WARNING: Agent attempting Tier {self.risk_tier} action![/bold red]")
                Console().print(f"[yellow]Tool:[/yellow] {self.__name__}")
                Console().print(f"[yellow]Payload:[/yellow] {validated_kwargs}")
                
                try:
                    approved = Confirm.ask("[bold red]Allow Execution?[/bold red]")
                except EOFError:
                    approved = False  # Auto-deny if running in background daemon/Docker without TTY
                    
                if not approved:
                    raise ToolGuardApprovalDeniedError(
                        f"Human rejected Tier {self.risk_tier} execution of '{self.__name__}'",
                        tool_name=self.__name__,
                        risk_tier=self.risk_tier,
                        correlation_id=correlation_id,
                    )

            # 3. Golden Trace Telemetry Intercept (ENTRY)
            from toolguard.core.tracer import get_active_tracer
            tracker = get_active_tracer()
            trace_node = None
            if tracker:
                # Appending the Node precisely at ENTRY guarantees perfect chronological execution graphs
                trace_node = tracker.record_entry(self.__name__, validated_kwargs)

            # 4. Execute the tool
            result = None
            try:
                result = self._func(**validated_kwargs)
            except Exception as e:
                result = f"<Exception: {type(e).__name__}>"
                raise
            finally:
                if trace_node and tracker:
                    tracker.record_exit(trace_node, result)

            # 5. Validate output
            result = self._validate_output(result, _correlation_id=correlation_id)

            # 6. Record success
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_success(latency)

            return result

        except SchemaValidationError:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            
            from toolguard.alerts.manager import dispatch_alert
            dispatch_alert(self.__name__, {"args": args, "kwargs": kwargs}, e)
            raise

    async def _acall(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous execution path for async def tools."""
        correlation_id = _new_correlation_id()
        start = time.perf_counter()

        try:
            # 1. Validate inputs (always synchronous — Pydantic is sync)
            validated_kwargs = self._validate_input(*args, **kwargs, _correlation_id=correlation_id)

            # 2. Human-In-The-Loop Security Check
            if getattr(self, "risk_tier", 0) >= 2 and os.environ.get("TOOLGUARD_AUTO_APPROVE") != "1":
                from rich.prompt import Confirm
                from rich.console import Console
                import asyncio

                Console().print(f"\n[bold red]⚠️  SECURITY WARNING: Agent attempting Tier {self.risk_tier} action![/bold red]")
                Console().print(f"[yellow]Tool:[/yellow] {self.__name__}")
                Console().print(f"[yellow]Payload:[/yellow] {validated_kwargs}")
                
                def _ask_confirm():
                    try:
                        return Confirm.ask("[bold red]Allow Execution?[/bold red]")
                    except EOFError:
                        return False # Auto-deny if no TTY terminal is attached
                    
                approved = await asyncio.to_thread(_ask_confirm)
                
                if not approved:
                    raise ToolGuardApprovalDeniedError(
                        f"Human rejected Tier {self.risk_tier} execution of '{self.__name__}'",
                        tool_name=self.__name__,
                        risk_tier=self.risk_tier,
                        correlation_id=correlation_id,
                    )

            # 3. Golden Trace Telemetry Intercept (ENTRY)
            from toolguard.core.tracer import get_active_tracer
            tracker = get_active_tracer()
            trace_node = None
            if tracker:
                trace_node = tracker.record_entry(self.__name__, validated_kwargs)

            # 4. Execute the async tool
            result = None
            try:
                result = await self._func(**validated_kwargs)
            except Exception as e:
                result = f"<Exception: {type(e).__name__}>"
                raise
            finally:
                if trace_node and tracker:
                    tracker.record_exit(trace_node, result)

            # 5. Validate output (always synchronous)
            result = self._validate_output(result, _correlation_id=correlation_id)

            # 6. Record success
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_success(latency)

            return result

        except SchemaValidationError:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            raise

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.stats.record_failure(latency)
            
            from toolguard.alerts.manager import dispatch_alert
            dispatch_alert(self.__name__, {"args": args, "kwargs": kwargs}, e)
            raise

    # ── Validation logic ─────────────────────────────────

    def _validate_input(
        self, *args: Any, _correlation_id: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        """Bind positional + keyword args, validate against input model."""
        # Bind args to signature — catch TypeError for wrong arg count/names
        try:
            bound = self._sig.bind(*args, **kwargs)
            bound.apply_defaults()
        except TypeError as e:
            raise SchemaValidationError(
                f"Input binding failed for '{self.__name__}': {e}",
                tool_name=self.__name__,
                direction="input",
                correlation_id=_correlation_id,
                suggestion=(
                    f"The agent passed arguments that don't match {self.__name__}'s signature. "
                    f"Expected: {self._sig}. Error: {e}"
                ),
            ) from e

        if not self._input_model:
            return dict(bound.arguments)

        try:
            validated = self._input_model(**bound.arguments)
            return validated.model_dump()
        except ValidationError as e:
            bad_payload = dict(bound.arguments)
            
            from toolguard.alerts.manager import dispatch_alert
            dispatch_alert(self.__name__, bad_payload, e)
            
            # Format a surgical suggestion
            specifics = []
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                msg = err["msg"]
                val = err.get("input", "<unknown>")
                specifics.append(f"Field '{loc}': {msg} (Got: {repr(val)} | Type: {type(val).__name__})")
            
            suggestion = "Agent hallucinated payload. Schema mismatch:\n" + "\n".join("  - " + s for s in specifics)

            raise SchemaValidationError(
                f"Input validation failed for '{self.__name__}'",
                tool_name=self.__name__,
                direction="input",
                validation_errors=e.errors(),
                correlation_id=_correlation_id,
                suggestion=suggestion,
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
            from toolguard.alerts.manager import dispatch_alert
            payload = result if isinstance(result, dict) else {"output": result}
            dispatch_alert(self.__name__, payload, e)
            
            # Format a surgical suggestion
            specifics = []
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                msg = err["msg"]
                val = err.get("input", "<unknown>")
                specifics.append(f"Field '{loc}': {msg} (Got: {repr(val)} | Type: {type(val).__name__})")
            
            suggestion = "Tool returned invalid data. Schema mismatch:\n" + "\n".join("  - " + s for s in specifics)

            raise SchemaValidationError(
                f"Output validation failed for '{self.__name__}'",
                tool_name=self.__name__,
                direction="output",
                validation_errors=e.errors(),
                correlation_id=_correlation_id,
                suggestion=suggestion,
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
    _func: Callable | None = None,
    schema: str | dict[str, Any] = "auto",
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
    version: str = "1.0.0",
    risk_tier: int = 0,
) -> Callable[[Callable], GuardedTool] | GuardedTool:
    """Decorator that wraps a function with ToolGuard validation.

    Supports both bare and parameterized usage:

        @create_tool
        def get_weather(location: str) -> dict:
            ...

        @create_tool(schema="auto", risk_tier=2)
        def delete_user(user_id: int) -> dict:
            ...

    Args:
        schema:       "auto" to generate from type hints, or a dict schema.
        input_model:  Explicit Pydantic model for inputs.
        output_model: Explicit Pydantic model for outputs.
        version:      Tool version string.
        risk_tier:    Risk tier level (0-3) for human-in-the-loop gating.
    """

    def decorator(func: Callable) -> GuardedTool:
        # Resolve input model
        resolved_input = input_model
        if resolved_input is None and schema == "auto":
            resolved_input = auto_generate_input_model(func)

        # Build schema
        tool_schema = auto_generate_schema(func, input_model=resolved_input, output_model=output_model)
        tool_schema.version = version

        return GuardedTool(
            func,
            input_model=resolved_input,
            output_model=output_model,
            schema=tool_schema,
            risk_tier=risk_tier,
        )

    # Support bare @create_tool usage (no parentheses)
    if _func is not None:
        return decorator(_func)

    return decorator
