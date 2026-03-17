"""
Tests for the storage module (ResultStore + SQLite persistence).

Verifies that:
  - Reports can be saved and retrieved
  - Chain history works with date filtering
  - Reliability trends compute correctly
  - get_all_chains() returns accurate summaries
  - clear_chain() and clear_all() work
"""
import os
import tempfile

import pytest

from toolguard.core.chain import test_chain as run_chain_test
from toolguard.core.validator import create_tool
from toolguard.storage.db import HistoryEntry, ReliabilityTrend, ResultStore


@pytest.fixture
def db_path():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def store(db_path):
    """Create a ResultStore backed by a temp database."""
    s = ResultStore(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def sample_report():
    """Generate a real ChainTestReport for testing storage."""
    @create_tool(schema="auto")
    def add_ten(value: int) -> dict:
        return {"result": value + 10}

    @create_tool(schema="auto")
    def double_it(result: int) -> dict:
        return {"final": result * 2}

    return run_chain_test(
        [add_ten, double_it],
        base_input={"value": 5},
        test_cases=["happy_path"],
        iterations=3,
        assert_reliability=0.0,
    )


class TestResultStore:

    def test_save_and_retrieve(self, store, sample_report):
        """Saved reports should be retrievable from history."""
        row_id = store.save_report(sample_report)
        assert row_id is not None
        assert row_id > 0

        history = store.get_chain_history(sample_report.chain_name, days=1)
        assert len(history) == 1
        assert history[0].chain_name == sample_report.chain_name
        assert history[0].reliability == sample_report.reliability

    def test_multiple_saves(self, store, sample_report):
        """Multiple saves should all be retrievable."""
        store.save_report(sample_report)
        store.save_report(sample_report)
        store.save_report(sample_report)

        history = store.get_chain_history(sample_report.chain_name, days=1)
        assert len(history) == 3

    def test_save_with_metadata(self, store, sample_report):
        """Metadata should be stored alongside the report."""
        row_id = store.save_report(
            sample_report,
            metadata={"git_hash": "abc123", "env": "ci"},
        )
        assert row_id > 0

    def test_get_all_chains(self, store, sample_report):
        """get_all_chains should return chain summaries."""
        store.save_report(sample_report)

        chains = store.get_all_chains()
        assert len(chains) == 1
        assert chains[0]["chain_name"] == sample_report.chain_name
        assert chains[0]["run_count"] == 1

    def test_clear_chain(self, store, sample_report):
        """clear_chain should remove only that chain's records."""
        store.save_report(sample_report)
        store.save_report(sample_report)

        deleted = store.clear_chain(sample_report.chain_name)
        assert deleted == 2

        history = store.get_chain_history(sample_report.chain_name, days=1)
        assert len(history) == 0

    def test_clear_all(self, store, sample_report):
        """clear_all should remove everything."""
        store.save_report(sample_report)
        deleted = store.clear_all()
        assert deleted == 1

        chains = store.get_all_chains()
        assert len(chains) == 0


class TestReliabilityTrend:

    def test_trend_from_history(self, store, sample_report):
        """ReliabilityTrend should compute from stored history."""
        store.save_report(sample_report)
        store.save_report(sample_report)

        trend = store.get_reliability_trend(sample_report.chain_name, days=1)
        assert isinstance(trend, ReliabilityTrend)
        assert len(trend.entries) == 2
        assert trend.average_reliability == sample_report.reliability

    def test_trend_summary(self, store, sample_report):
        """Trend summary should return a readable string."""
        store.save_report(sample_report)
        trend = store.get_reliability_trend(sample_report.chain_name, days=1)

        summary = trend.summary()
        assert sample_report.chain_name in summary
        assert "Runs:" in summary

    def test_empty_trend(self, store):
        """Empty trend should handle gracefully."""
        trend = store.get_reliability_trend("nonexistent")
        assert trend.average_reliability == 0.0
        assert trend.latest is None
        assert "No history" in trend.summary()


class TestHistoryEntry:

    def test_properties(self, store, sample_report):
        """HistoryEntry properties should work correctly."""
        store.save_report(sample_report)
        history = store.get_chain_history(sample_report.chain_name, days=1)
        entry = history[0]

        assert isinstance(entry, HistoryEntry)
        assert isinstance(entry.reliability_pct, str)
        assert "%" in entry.reliability_pct
        assert entry.status_icon in ["🟢", "🔵", "🟡", "🟠", "🔴"]


class TestContextManager:

    def test_context_manager(self, db_path):
        """ResultStore should work as a context manager."""
        with ResultStore(db_path=db_path) as store:
            chains = store.get_all_chains()
            assert isinstance(chains, list)
