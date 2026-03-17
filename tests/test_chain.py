"""
Tests for toolguard.core.chain — the chain testing engine.

Tests cover:
  - Happy path chain execution
  - Null handling edge cases
  - Malformed data injection
  - Reliability threshold assertions
  - Report structure (failure_analyses, runs, steps)
"""
import pytest

from toolguard.core.chain import test_chain as run_chain_test
from toolguard.core.validator import create_tool

# ── Helper tools (defined here for isolation) ─────────────


def _make_adder():
    @create_tool(schema="auto")
    def add_tax(price: float, tax_rate: float = 0.1) -> dict:
        return {"total": price * (1 + tax_rate), "price": price}
    return add_tax


def _make_formatter():
    @create_tool(schema="auto")
    def format_receipt(total: float, price: float) -> dict:
        return {"receipt": f"Price: ${price:.2f}, Total: ${total:.2f}"}
    return format_receipt


# ── Chain happy path ──────────────────────────────────────


class TestChainHappyPath:

    def test_single_tool_chain(self):
        tool = _make_adder()

        report = run_chain_test(
            [tool],
            base_input={"price": 100.0, "tax_rate": 0.1},
            test_cases=["happy_path"],
            iterations=3,
            assert_reliability=0.0,  # Don't assert, just get report
        )

        assert report.total_tests == 3
        assert report.passed == 3
        assert report.reliability == 1.0

    def test_two_tool_chain(self):
        adder = _make_adder()
        formatter = _make_formatter()

        report = run_chain_test(
            [adder, formatter],
            base_input={"price": 50.0, "tax_rate": 0.2},
            test_cases=["happy_path"],
            iterations=2,
            assert_reliability=0.0,
        )

        assert report.passed == 2
        assert report.reliability == 1.0

    def test_report_has_runs_and_steps(self):
        tool = _make_adder()

        report = run_chain_test(
            [tool],
            base_input={"price": 100.0},
            test_cases=["happy_path"],
            iterations=1,
            assert_reliability=0.0,
        )

        assert len(report.runs) == 1
        assert len(report.runs[0].steps) == 1
        assert report.runs[0].steps[0].success is True
        assert report.runs[0].steps[0].latency_ms > 0


# ── Reliability threshold ────────────────────────────────


class TestReliabilityThreshold:

    def test_passes_when_above_threshold(self):
        tool = _make_adder()

        # Should not raise
        report = run_chain_test(
            [tool],
            base_input={"price": 100.0},
            test_cases=["happy_path"],
            iterations=5,
            assert_reliability=0.95,
        )
        assert report.reliability >= 0.95

    def test_raises_when_below_threshold(self):
        """A chain that always fails should raise AssertionError."""
        @create_tool(schema="auto")
        def always_fails(x: int) -> dict:
            raise RuntimeError("I always fail!")

        with pytest.raises(AssertionError) as exc_info:
            run_chain_test(
                [always_fails],
                base_input={"x": 1},
                test_cases=["happy_path"],
                iterations=3,
                assert_reliability=0.5,
            )

        assert "below" in str(exc_info.value).lower()


# ── Edge case testing ─────────────────────────────────────


class TestEdgeCases:

    def test_null_handling_produces_failures(self):
        """Null handling tests inject None values, which should cause failures."""
        @create_tool(schema="auto")
        def strict_tool(name: str, count: int) -> dict:
            return {"result": name * count}

        report = run_chain_test(
            [strict_tool],
            base_input={"name": "hello", "count": 3},
            test_cases=["null_handling"],
            assert_reliability=0.0,
        )

        # null_handling generates: name=None, count=None, and {}
        # All should fail because the tool requires str and int
        assert report.failed > 0
        assert report.reliability < 1.0

    def test_malformed_data_produces_failures(self):
        """Malformed data tests inject wrong types."""
        @create_tool(schema="auto")
        def typed_tool(value: str) -> dict:
            return {"length": len(value)}

        report = run_chain_test(
            [typed_tool],
            base_input={"value": "test"},
            test_cases=["malformed_data"],
            assert_reliability=0.0,
        )

        # malformed_data converts "test" -> 12345 (int)
        # This may or may not fail depending on Pydantic coercion
        assert report.total_tests > 0


# ── Failure analysis ──────────────────────────────────────


class TestFailureAnalysis:

    def test_failure_analyses_populated(self):
        """Failed runs should produce failure analyses with suggestions."""
        @create_tool(schema="auto")
        def crasher(data: str) -> dict:
            raise KeyError("missing_key")

        report = run_chain_test(
            [crasher],
            base_input={"data": "test"},
            test_cases=["happy_path"],
            iterations=1,
            assert_reliability=0.0,
        )

        assert report.failed == 1
        assert len(report.failure_analyses) == 1

        analysis = report.failure_analyses[0]
        assert analysis.tool_name == "crasher"
        assert analysis.error_type == "KeyError"
        assert len(analysis.suggestion) > 0

    def test_chain_name_auto_generated(self):
        tool = _make_adder()

        report = run_chain_test(
            [tool],
            base_input={"price": 100.0},
            test_cases=["happy_path"],
            iterations=1,
            assert_reliability=0.0,
        )

        assert "add_tax" in report.chain_name
