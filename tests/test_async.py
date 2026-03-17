"""
Tests for async support in ToolGuard.

Verifies that:
  - @create_tool works with async def functions
  - GuardedTool correctly detects and handles async tools
  - test_chain() handles mixed sync + async chains transparently
  - Stats tracking works identically for async tools
"""
import asyncio
import pytest
from toolguard.core.validator import create_tool, GuardedTool
from toolguard.core.chain import test_chain as run_chain_test
from toolguard.core.errors import SchemaValidationError


# ── Async GuardedTool ─────────────────────────────────────


class TestAsyncGuardedTool:

    def test_detects_async_function(self):
        @create_tool(schema="auto")
        async def async_fetch(url: str) -> dict:
            return {"data": url}

        assert isinstance(async_fetch, GuardedTool)
        assert async_fetch._is_async is True

    def test_sync_tool_not_marked_async(self):
        @create_tool(schema="auto")
        def sync_fetch(url: str) -> dict:
            return {"data": url}

        assert sync_fetch._is_async is False

    def test_async_tool_returns_coroutine(self):
        @create_tool(schema="auto")
        async def async_add(x: int, y: int = 0) -> dict:
            return {"sum": x + y}

        result = async_add(x=3, y=4)
        # __call__ returns a coroutine for async tools
        assert asyncio.iscoroutine(result)
        # Clean up the coroutine
        actual = asyncio.run(result)
        assert actual == {"sum": 7}

    def test_async_tool_validates_input(self):
        @create_tool(schema="auto")
        async def strict_async(value: int) -> dict:
            return {"value": value}

        with pytest.raises(SchemaValidationError) as exc_info:
            asyncio.run(strict_async(value="not_a_number"))

        assert "Input validation failed" in str(exc_info.value)

    def test_async_tool_tracks_stats(self):
        @create_tool(schema="auto")
        async def counted_tool(x: int) -> dict:
            if x < 0:
                raise ValueError("Negative!")
            return {"result": x}

        # Success
        asyncio.run(counted_tool(x=5))
        assert counted_tool.stats.total_calls == 1
        assert counted_tool.stats.success_count == 1

        # Failure
        with pytest.raises(ValueError):
            asyncio.run(counted_tool(x=-1))

        assert counted_tool.stats.total_calls == 2
        assert counted_tool.stats.failure_count == 1
        assert counted_tool.stats.success_rate == 0.5


# ── Async Chain Testing ──────────────────────────────────


class TestAsyncChainTesting:

    def test_pure_async_chain(self):
        """test_chain with all async tools should work transparently."""
        @create_tool(schema="auto")
        async def async_step_a(value: int) -> dict:
            return {"doubled": value * 2}

        @create_tool(schema="auto")
        async def async_step_b(doubled: int) -> dict:
            return {"message": f"Result is {doubled}"}

        report = run_chain_test(
            [async_step_a, async_step_b],
            base_input={"value": 5},
            test_cases=["happy_path"],
            iterations=3,
            assert_reliability=0.0,
        )

        assert report.passed == 3
        assert report.reliability == 1.0

    def test_mixed_sync_async_chain(self):
        """A chain with both sync and async tools should work."""
        @create_tool(schema="auto")
        def sync_parser(data: str) -> dict:
            return {"length": len(data), "data": data}

        @create_tool(schema="auto")
        async def async_processor(length: int, data: str) -> dict:
            return {"summary": f"{data[:10]}... ({length} chars)"}

        report = run_chain_test(
            [sync_parser, async_processor],
            base_input={"data": "Hello World Test Data"},
            test_cases=["happy_path"],
            iterations=2,
            assert_reliability=0.0,
        )

        assert report.passed == 2
        assert report.reliability == 1.0

    def test_async_chain_catches_failures(self):
        """Edge-case tests should catch failures in async tools too."""
        @create_tool(schema="auto")
        async def fragile_async(name: str, count: int) -> dict:
            return {"result": name * count}

        report = run_chain_test(
            [fragile_async],
            base_input={"name": "test", "count": 3},
            test_cases=["null_handling"],
            assert_reliability=0.0,
        )

        # null_handling injects None values, causing failures
        assert report.failed > 0
        assert len(report.failure_analyses) > 0
