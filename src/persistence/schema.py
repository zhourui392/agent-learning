"""SQLite schema management -- idempotent table creation and version migration."""

from __future__ import annotations

import sqlite3
from typing import Optional

SCHEMA_VERSION = 1

_CREATE_STATEMENTS = [
    # -- shared memory
    """
    CREATE TABLE IF NOT EXISTS shared_memory (
        key          TEXT PRIMARY KEY,
        value        TEXT NOT NULL,
        version      INTEGER NOT NULL,
        writer_role  TEXT NOT NULL,
        updated_at   REAL NOT NULL,
        expires_at   REAL
    )
    """,
    # -- circuit state
    """
    CREATE TABLE IF NOT EXISTS circuit_state (
        tool_name          TEXT PRIMARY KEY,
        state              TEXT NOT NULL,
        failure_count      INTEGER NOT NULL DEFAULT 0,
        success_count      INTEGER NOT NULL DEFAULT 0,
        half_open_successes INTEGER NOT NULL DEFAULT 0,
        last_failure_time  REAL NOT NULL DEFAULT 0.0,
        last_state_change  REAL NOT NULL,
        total_calls        INTEGER NOT NULL DEFAULT 0,
        total_failures     INTEGER NOT NULL DEFAULT 0,
        total_rejections   INTEGER NOT NULL DEFAULT 0
    )
    """,
    # -- config entries (current)
    """
    CREATE TABLE IF NOT EXISTS config_entries (
        namespace    TEXT NOT NULL,
        key          TEXT NOT NULL,
        value        TEXT NOT NULL,
        version      INTEGER NOT NULL,
        config_type  TEXT NOT NULL,
        updated_at   REAL NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (namespace, key)
    )
    """,
    # -- config history
    """
    CREATE TABLE IF NOT EXISTS config_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        namespace    TEXT NOT NULL,
        key          TEXT NOT NULL,
        value        TEXT NOT NULL,
        version      INTEGER NOT NULL,
        config_type  TEXT NOT NULL,
        updated_at   REAL NOT NULL,
        description  TEXT NOT NULL DEFAULT ''
    )
    """,
    # -- sessions
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id   TEXT PRIMARY KEY,
        instance_id  TEXT NOT NULL,
        state        TEXT NOT NULL,
        payload      TEXT NOT NULL,
        created_at   REAL NOT NULL,
        updated_at   REAL NOT NULL,
        expires_at   REAL
    )
    """,
    # -- instance registry
    """
    CREATE TABLE IF NOT EXISTS instances (
        instance_id  TEXT PRIMARY KEY,
        hostname     TEXT NOT NULL DEFAULT '',
        started_at   REAL NOT NULL,
        last_heartbeat REAL NOT NULL,
        status       TEXT NOT NULL DEFAULT 'alive'
    )
    """,
    # -- schema version tracking
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        id           INTEGER PRIMARY KEY CHECK (id = 1),
        version      INTEGER NOT NULL
    )
    """,
]


class SchemaManager:
    """Idempotent SQLite schema creation and version migration."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def ensure_schema(self) -> int:
        """Create all tables if missing and return current schema version.

        This method is idempotent -- safe to call on every startup.
        """
        self._conn.execute("PRAGMA journal_mode=WAL")

        for stmt in _CREATE_STATEMENTS:
            self._conn.execute(stmt)

        current = self._get_version()
        if current is None:
            self._conn.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?)",
                (SCHEMA_VERSION,),
            )
            self._conn.commit()
            return SCHEMA_VERSION

        if current < SCHEMA_VERSION:
            self._migrate(current, SCHEMA_VERSION)

        self._conn.commit()
        return self._get_version() or SCHEMA_VERSION

    def _get_version(self) -> Optional[int]:
        try:
            row = self._conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
            return row[0] if row else None
        except sqlite3.OperationalError:
            return None

    def _migrate(self, from_version: int, to_version: int) -> None:
        """Apply incremental migrations.  Currently a placeholder."""
        self._conn.execute(
            "UPDATE schema_version SET version = ? WHERE id = 1",
            (to_version,),
        )
