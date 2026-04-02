"""
toolguard.core.drift_store
~~~~~~~~~~~~~~~~~~~~~~~~~~

SQLite-backed persistent storage for schema fingerprints.

Extends the existing .toolguard/ directory with a dedicated
fingerprints table for tracking schema evolution over time.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from toolguard.core.drift import SchemaFingerprint


# ──────────────────────────────────────────────────────────
#  Schema
# ──────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_fingerprints_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name       TEXT NOT NULL,
    model           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    prompt          TEXT NOT NULL,
    json_schema     TEXT NOT NULL,
    sample_output   TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    UNIQUE(tool_name, model)
);

CREATE INDEX IF NOT EXISTS idx_fp_tool_v2 ON schema_fingerprints_v2(tool_name);
CREATE INDEX IF NOT EXISTS idx_fp_model_v2 ON schema_fingerprints_v2(model);
"""


class FingerprintStore:
    """SQLite-backed storage for schema fingerprints.

    Args:
        db_path: Path to the SQLite database.
                 Defaults to .toolguard/drift.db
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_dir = Path(".toolguard")
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "drift.db"

        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=10.0
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        # 30-Second Thread Queuing completely prevents 'Database is locked' crashes
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── Write ─────────────────────────────────────────────

    def save_fingerprint(self, fp: SchemaFingerprint) -> None:
        """Save or update a schema fingerprint.

        Hardened: Normalizes tool_name to prevent casing-based duplicate baseline evasion.
        """
        name = fp.tool_name.strip().casefold()
        self._conn.execute(
            """
            INSERT INTO schema_fingerprints_v2
                (tool_name, model, created_at, prompt,
                 json_schema, sample_output, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tool_name, model)
            DO UPDATE SET
                created_at = excluded.created_at,
                prompt = excluded.prompt,
                json_schema = excluded.json_schema,
                sample_output = excluded.sample_output,
                checksum = excluded.checksum
            """,
            (
                name,
                fp.model,
                fp.timestamp,
                fp.prompt,
                json.dumps(fp.json_schema),
                json.dumps(fp.sample_output, default=str),
                fp.checksum,
            ),
        )
        self._conn.commit()

    # ── Read ──────────────────────────────────────────────

    def get_fingerprint(
        self, tool_name: str, model: str
    ) -> SchemaFingerprint | None:
        """Retrieve a stored fingerprint by tool and model.

        Hardened: Uses normalized tool_name lookup.
        """
        name = tool_name.strip().casefold()
        row = self._conn.execute(
            """
            SELECT * FROM schema_fingerprints_v2
            WHERE tool_name = ? AND model = ?
            """,
            (name, model),
        ).fetchone()

        if not row:
            return None

        return SchemaFingerprint(
            tool_name=row["tool_name"],
            prompt=row["prompt"],
            model=row["model"],
            timestamp=row["created_at"],
            json_schema=json.loads(row["json_schema"]),
            sample_output=json.loads(row["sample_output"]),
            checksum=row["checksum"],
        )

    def get_latest_fingerprint_for_tool(
        self, tool_name: str
    ) -> SchemaFingerprint | None:
        """Retrieve the absolute most recent fingerprint for a specific tool.

        Hardened: Uses indexed native SQLite filtering to prevent O(N) 
        memory exhaustion in the live proxy path.
        """
        name = tool_name.strip().casefold()
        row = self._conn.execute(
            """
            SELECT * FROM schema_fingerprints_v2
            WHERE tool_name = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (name,),
        ).fetchone()

        if not row:
            return None

        return SchemaFingerprint(
            tool_name=row["tool_name"],
            prompt=row["prompt"],
            model=row["model"],
            timestamp=row["created_at"],
            json_schema=json.loads(row["json_schema"]),
            sample_output=json.loads(row["sample_output"]),
            checksum=row["checksum"],
        )

    def get_all_fingerprints(self) -> list[SchemaFingerprint]:
        """Retrieve all stored fingerprints."""
        rows = self._conn.execute(
            "SELECT * FROM schema_fingerprints_v2 ORDER BY created_at DESC"
        ).fetchall()

        return [
            SchemaFingerprint(
                tool_name=row["tool_name"],
                prompt=row["prompt"],
                model=row["model"],
                timestamp=row["created_at"],
                json_schema=json.loads(row["json_schema"]),
                sample_output=json.loads(row["sample_output"]),
                checksum=row["checksum"],
            )
            for row in rows
        ]

    def delete_fingerprint(self, tool_name: str, model: str) -> int:
        """Delete all fingerprints for a specific tool+model combo."""
        name = tool_name.strip().casefold()
        cursor = self._conn.execute(
            "DELETE FROM schema_fingerprints_v2 WHERE tool_name = ? AND model = ?",
            (name, model),
        )
        self._conn.commit()
        return cursor.rowcount

    # ── Lifecycle ─────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FingerprintStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
