"""
Tests for toolguard.core.validator — the @create_tool decorator.

Tests cover:
  - Basic wrapping and GuardedTool identity
  - Automatic Pydantic input validation
  - Output model validation
  - SchemaValidationError for bad inputs
  - ToolStats tracking (success/failure counts)
  - Schema auto-generation from type hints
"""
import pytest
from pydantic import BaseModel

from toolguard.core.validator import create_tool, GuardedTool
from toolguard.core.errors import SchemaValidationError


# ── Basic decorator behaviour ─────────────────────────────


class TestCreateToolBasic:

    def test_returns_guarded_tool(self):
        @create_tool(schema="auto")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        assert isinstance(greet, GuardedTool)

    def test_preserves_function_name(self):
        @create_tool(schema="auto")
        def my_unique_tool(x: int) -> int:
            return x

        assert greet.__name__ == "my_unique_tool"  if False else True
        assert my_unique_tool.__name__ == "my_unique_tool"

    def test_preserves_docstring(self):
        @create_tool(schema="auto")
        def documented_tool(x: int) -> int:
            """This tool does math."""
            return x * 2

        assert documented_tool.__doc__ == "This tool does math."

    def test_schema_auto_generated(self):
        @create_tool(schema="auto")
        def add(a: int, b: int = 0) -> int:
            return a + b

        assert add.schema is not None
        assert add.schema.name == "add"

    def test_callable_directly(self):
        """GuardedTool should be callable like the original function."""
        @create_tool(schema="auto")
        def double(x: int) -> int:
            return x * 2

        result = double(x=5)
        assert result == 10


# ── Input validation ──────────────────────────────────────


class TestInputValidation:

    def test_valid_inputs_pass(self):
        @create_tool(schema="auto")
        def multiply(x: int, y: int = 2) -> int:
            return x * y

        assert multiply(x=5, y=3) == 15
        assert multiply(x=5) == 10

    def test_type_coercion(self):
        """Pydantic should coerce compatible types (e.g., '5' -> 5)."""
        @create_tool(schema="auto")
        def square(n: int) -> int:
            return n * n

        # String "5" should be coerced to int 5
        assert square(n="5") == 25

    def test_invalid_type_raises_schema_error(self):
        @create_tool(schema="auto")
        def require_int(x: int) -> int:
            return x

        with pytest.raises(SchemaValidationError) as exc_info:
            require_int(x="not_a_number")

        assert "Input validation failed" in str(exc_info.value)
        assert exc_info.value.direction == "input"
        assert exc_info.value.tool_name == "require_int"


# ── Output validation ────────────────────────────────────


class TestOutputValidation:

    def test_valid_output_passes(self):
        class PersonOutput(BaseModel):
            name: str
            age: int

        @create_tool(schema="auto", output_model=PersonOutput)
        def get_person(person_id: int) -> dict:
            return {"name": "Bob", "age": 30}

        result = get_person(person_id=1)
        assert result == {"name": "Bob", "age": 30}

    def test_invalid_output_raises_schema_error(self):
        class StrictOutput(BaseModel):
            value: int

        @create_tool(schema="auto", output_model=StrictOutput)
        def bad_output(x: int) -> dict:
            return {"value": "not_an_int"}

        with pytest.raises(SchemaValidationError) as exc_info:
            bad_output(x=1)

        assert "Output validation failed" in str(exc_info.value)
        assert exc_info.value.direction == "output"


# ── Stats tracking ───────────────────────────────────────


class TestToolStats:

    def test_initial_stats_zero(self):
        @create_tool(schema="auto")
        def noop(x: int = 0) -> int:
            return x

        assert noop.stats.total_calls == 0
        assert noop.stats.success_count == 0
        assert noop.stats.failure_count == 0

    def test_success_increments(self):
        @create_tool(schema="auto")
        def add_one(x: int) -> int:
            return x + 1

        add_one(x=1)
        add_one(x=2)
        add_one(x=3)

        assert add_one.stats.total_calls == 3
        assert add_one.stats.success_count == 3
        assert add_one.stats.failure_count == 0
        assert add_one.stats.success_rate == 1.0

    def test_failure_increments(self):
        @create_tool(schema="auto")
        def risky(x: int) -> int:
            if x < 0:
                raise ValueError("Negative!")
            return x

        risky(x=5)  # Success

        with pytest.raises(ValueError):
            risky(x=-1)  # Failure

        assert risky.stats.total_calls == 2
        assert risky.stats.success_count == 1
        assert risky.stats.failure_count == 1
        assert risky.stats.success_rate == 0.5

    def test_latency_tracked(self):
        import time

        @create_tool(schema="auto")
        def slow_tool(ms: int = 50) -> dict:
            time.sleep(ms / 1000)
            return {"waited": ms}

        slow_tool(ms=50)

        assert slow_tool.stats.avg_latency_ms >= 40  # Allow some variance


# ── Unwrap ────────────────────────────────────────────────


class TestUnwrap:

    def test_unwrap_returns_original(self):
        def original_func(x: int) -> int:
            return x * 3

        guarded = create_tool(schema="auto")(original_func)
        unwrapped = guarded.unwrap()

        # Unwrapped function should be the original, no validation
        assert unwrapped is original_func
        assert unwrapped(x=5) == 15
