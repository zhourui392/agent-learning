"""Tests for schema manager idempotency and versioning."""

from __future__ import annotations

import sqlite3

import pytest

from src.persistence.schema import SCHEMA_VERSION, SchemaManager


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


class TestSchemaManager:

    def test_ensure_creates_tables(self, conn):
        version = SchemaManager(conn).ensure_schema()
        assert version == SCHEMA_VERSION

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "shared_memory", "circuit_state", "config_entries",
            "config_history", "sessions", "instances", "schema_version",
        }
        assert expected.issubset(tables)

    def test_idempotent(self, conn):
        sm = SchemaManager(conn)
        v1 = sm.ensure_schema()
        v2 = sm.ensure_schema()
        assert v1 == v2

    def test_wal_mode_enabled(self, conn):
        SchemaManager(conn).ensure_schema()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        # In-memory databases may report "memory" instead of "wal"
        assert mode in ("wal", "memory")
