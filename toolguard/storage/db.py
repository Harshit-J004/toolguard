"""
toolguard.storage.db
~~~~~~~~~~~~~~~~~~~~

SQLite-backed storage engine for ToolGuard test results.

Stores chain test results persistently so users can track
reliability trends over time. Uses Python's built-in sqlite3
module — zero external dependencies.

Usage:
    from toolguard.storage import ResultStore

    store = ResultStore()                     # defaults to .toolguard/history.db
    store.save_report(report)                 # persist a ChainTestReport
    history = store.get_chain_history("my_chain", days=30)
    trend = store.get_reliability_trend("my_chain")
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toolguard.core.report import ChainTestReport

# ──────────────────────────────────────────────────────────
#  Schema
# ──────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS test_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_name      TEXT NOT NULL,
    run_at          TEXT NOT NULL DEFAULT (datetime('now')),
    total_tests     INTEGER NOT NULL,
    passed          INTEGER NOT NULL,
    failed          INTEGER NOT NULL,
    reliability     REAL NOT NULL,
    threshold       REAL NOT NULL,
    passed_threshold INTEGER NOT NULL,
    tool_names      TEXT NOT NULL,
    top_failures    TEXT,
    run_duration_ms REAL,
    metadata        TEXT
);

CREATE INDEX IF NOT EXISTS idx_chain_name ON test_runs(chain_name);
CREATE INDEX IF NOT EXISTS idx_run_at ON test_runs(run_at);
"""


# ──────────────────────────────────────────────────────────
#  Data models for query results
# ──────────────────────────────────────────────────────────

@dataclass
class HistoryEntry:
    """A single historical test run."""
    id: int
    chain_name: str
    run_at: str
    total_tests: int
    passed: int
    failed: int
    reliability: float
    threshold: float
    passed_threshold: bool
    tool_names: list[str]
    top_failures: list[dict]

    @property
    def reliability_pct(self) -> str:
        return f"{self.reliability:.1%}"

    @property
    def status_icon(self) -> str:
        if self.reliability >= 0.95:
            return "🟢"
        elif self.reliability >= 0.85:
            return "🔵"
        elif self.reliability >= 0.70:
            return "🟡"
        elif self.reliability >= 0.50:
            return "🟠"
        else:
            return "🔴"


@dataclass
class ReliabilityTrend:
    """Reliability trend for a chain over time."""
    chain_name: str
    entries: list[HistoryEntry]

    @property
    def latest(self) -> HistoryEntry | None:
        return self.entries[-1] if self.entries else None

    @property
    def average_reliability(self) -> float:
        if not self.entries:
            return 0.0
        return sum(e.reliability for e in self.entries) / len(self.entries)

    @property
    def improving(self) -> bool:
        """True if reliability is trending upward (last 3 runs)."""
        if len(self.entries) < 2:
            return True
        recent = self.entries[-3:]
        return recent[-1].reliability >= recent[0].reliability

    @property
    def trend_direction(self) -> str:
        if len(self.entries) < 2:
            return "→ stable"
        diff = self.entries[-1].reliability - self.entries[0].reliability
        if diff > 0.02:
            return f"↑ improving (+{diff:.1%})"
        elif diff < -0.02:
            return f"↓ declining ({diff:.1%})"
        return "→ stable"

    def summary(self) -> str:
        """Human-readable trend summary."""
        if not self.entries:
            return f"No history for '{self.chain_name}'"
        lines = [
            f"Chain: {self.chain_name}",
            f"Runs:  {len(self.entries)}",
            f"Avg:   {self.average_reliability:.1%}",
            f"Trend: {self.trend_direction}",
        ]
        if self.latest:
            lines.append(f"Last:  {self.latest.reliability_pct} ({self.latest.run_at})")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
#  ResultStore — the main storage API
# ──────────────────────────────────────────────────────────

class ResultStore:
    """SQLite-backed persistent storage for chain test results.

    Args:
        db_path: Path to SQLite database file.
                 Defaults to .toolguard/history.db in the current directory.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_dir = Path(".toolguard")
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "history.db"

        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── Write ─────────────────────────────────────────────

    def save_report(self, report: ChainTestReport, *, metadata: dict[str, Any] | None = None) -> int:
        """Persist a ChainTestReport to the database.

        Args:
            report:   The chain test report to store.
            metadata: Optional extra data (environment, git hash, etc.)

        Returns:
            The ID of the inserted row.
        """
        total_latency = sum(r.total_latency_ms for r in report.runs)

        cursor = self._conn.execute(
            """
            INSERT INTO test_runs
                (chain_name, total_tests, passed, failed, reliability,
                 threshold, passed_threshold, tool_names, top_failures,
                 run_duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.chain_name,
                report.total_tests,
                report.passed,
                report.failed,
                report.reliability,
                report.reliability_threshold,
                1 if report.passed_threshold else 0,
                json.dumps(report.tool_names),
                json.dumps(report.top_failures[:5]),
                total_latency,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # ── Read ──────────────────────────────────────────────

    def get_chain_history(
        self,
        chain_name: str,
        *,
        days: int = 30,
        limit: int = 100,
    ) -> list[HistoryEntry]:
        """Get historical test runs for a chain.

        Args:
            chain_name: Name of the chain to query.
            days:       How far back to look (default: 30 days).
            limit:      Maximum number of results.

        Returns:
            List of HistoryEntry, oldest first.
        """
        modifier = f"-{days} days"
        rows = self._conn.execute(
            """
            SELECT * FROM test_runs
            WHERE chain_name = ? AND run_at >= datetime('now', ?)
            ORDER BY run_at ASC
            LIMIT ?
            """,
            (chain_name, modifier, limit),
        ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def get_reliability_trend(self, chain_name: str, *, days: int = 30) -> ReliabilityTrend:
        """Get the reliability trend for a chain over time.

        Args:
            chain_name: Name of the chain.
            days:       How far back to analyze.

        Returns:
            ReliabilityTrend with computed statistics.
        """
        entries = self.get_chain_history(chain_name, days=days)
        return ReliabilityTrend(chain_name=chain_name, entries=entries)

    def get_all_chains(self) -> list[dict[str, Any]]:
        """List all chains that have been tested, with their latest stats.

        Returns:
            List of dicts with chain_name, run_count, latest_reliability, last_run.
        """
        rows = self._conn.execute(
            """
            SELECT
                chain_name,
                COUNT(*) as run_count,
                MAX(run_at) as last_run,
                AVG(reliability) as avg_reliability
            FROM test_runs
            GROUP BY chain_name
            ORDER BY last_run DESC
            """
        ).fetchall()

        results = []
        for row in rows:
            # Get latest reliability for this chain
            latest = self._conn.execute(
                "SELECT reliability FROM test_runs WHERE chain_name = ? ORDER BY run_at DESC LIMIT 1",
                (row["chain_name"],),
            ).fetchone()

            results.append({
                "chain_name": row["chain_name"],
                "run_count": row["run_count"],
                "last_run": row["last_run"],
                "avg_reliability": row["avg_reliability"],
                "latest_reliability": latest["reliability"] if latest else 0.0,
            })

        return results

    # ── Utilities ─────────────────────────────────────────

    def clear_chain(self, chain_name: str) -> int:
        """Delete all records for a specific chain.

        Returns:
            Number of deleted rows.
        """
        cursor = self._conn.execute(
            "DELETE FROM test_runs WHERE chain_name = ?",
            (chain_name,),
        )
        self._conn.commit()
        return cursor.rowcount

    def clear_all(self) -> int:
        """Delete ALL records. Use with caution.

        Returns:
            Number of deleted rows.
        """
        cursor = self._conn.execute("DELETE FROM test_runs")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> ResultStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        """Convert a database row to a HistoryEntry."""
        return HistoryEntry(
            id=row["id"],
            chain_name=row["chain_name"],
            run_at=row["run_at"],
            total_tests=row["total_tests"],
            passed=row["passed"],
            failed=row["failed"],
            reliability=row["reliability"],
            threshold=row["threshold"],
            passed_threshold=bool(row["passed_threshold"]),
            tool_names=json.loads(row["tool_names"]),
            top_failures=json.loads(row["top_failures"]) if row["top_failures"] else [],
        )
