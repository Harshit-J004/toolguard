"""
toolguard.core.tracer
~~~~~~~~~~~~~~~~~~~~~

OpenTelemetry integration for tool call tracing.

Provides automatic span creation for every tool execution,
capturing inputs, outputs, latency, and errors in a vendor-neutral
format that works with Jaeger, Zipkin, Datadog, and more.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

# OpenTelemetry imports (graceful fallback if not installed)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SpanExporter,
    )
    from opentelemetry.trace import StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


# ──────────────────────────────────────────────────────────
#  Tracing Initialisation
# ──────────────────────────────────────────────────────────

_tracer: Any = None


def init_tracing(
    *,
    service_name: str = "toolguard",
    exporter: Any | None = None,
) -> None:
    """Initialize OpenTelemetry tracing for ToolGuard.

    Call this once at application startup to enable tracing.
    If OpenTelemetry is not installed, this is a no-op.

    Args:
        service_name: Service name reported in traces.
        exporter:     Custom SpanExporter. Defaults to ConsoleSpanExporter.
    """
    global _tracer

    if not _OTEL_AVAILABLE:
        return

    provider = TracerProvider()

    if exporter is None:
        exporter = ConsoleSpanExporter()

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer(service_name, "0.1.0")


def get_tracer() -> Any:
    """Get the current tracer (or a no-op if not initialized)."""
    global _tracer

    if _tracer is not None:
        return _tracer

    if _OTEL_AVAILABLE:
        _tracer = trace.get_tracer("toolguard", "0.1.0")
        return _tracer

    return _NoOpTracer()


# ──────────────────────────────────────────────────────────
#  @trace_tool Decorator
# ──────────────────────────────────────────────────────────

def trace_tool(func: Callable) -> Callable:
    """Decorator that adds OpenTelemetry tracing to a tool function.

    Creates a span for each invocation with attributes:
        tool.name, tool.input, tool.output, tool.success, tool.latency_ms

    Usage:
        @trace_tool
        def get_weather(location: str) -> dict:
            ...
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        tool_name = getattr(func, "__name__", "unknown_tool")

        if isinstance(tracer, _NoOpTracer):
            return func(*args, **kwargs)

        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.input", _safe_str(kwargs or args))

            start = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000

                span.set_attribute("tool.success", True)
                span.set_attribute("tool.output", _safe_str(result))
                span.set_attribute("tool.latency_ms", round(latency_ms, 2))
                span.set_status(StatusCode.OK)

                return result

            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000

                span.set_attribute("tool.success", False)
                span.set_attribute("tool.latency_ms", round(latency_ms, 2))
                span.set_attribute("tool.error", str(exc))
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)

                raise

    return wrapper


def trace_chain(chain_name: str = "tool_chain") -> Callable:
    """Decorator for tracing an entire chain execution as a parent span."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()

            if isinstance(tracer, _NoOpTracer):
                return func(*args, **kwargs)

            with tracer.start_as_current_span(f"chain.{chain_name}") as span:
                span.set_attribute("chain.name", chain_name)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(StatusCode.OK)
                    return result
                except Exception as exc:
                    span.set_status(StatusCode.ERROR, str(exc))
                    span.record_exception(exc)
                    raise

        return wrapper

    return decorator


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────

def _safe_str(obj: Any, max_len: int = 200) -> str:
    """Safely convert an object to a truncated string for span attributes."""
    try:
        s = str(obj)
        return s[:max_len] if len(s) > max_len else s
    except Exception:
        return "<unserializable>"


class _NoOpTracer:
    """Fallback tracer when OpenTelemetry is not available."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> "_NoOpSpan":
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span for when tracing is disabled."""

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass
