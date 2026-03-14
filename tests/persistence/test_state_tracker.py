"""Tests for the unified state tracker."""

from __future__ import annotations

import sqlite3
import time

import pytest

from src.persistence.instance_registry import InstanceRegistry
from src.persistence.schema import SchemaManager
from src.persistence.serialization import serialize
from src.persistence.state_tracker import StateTracker


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestStateTracker:

    def test_empty_snapshot(self, conn):
        tracker = StateTracker(conn)
        snap = tracker.snapshot()
        assert snap.shared_memory_keys == 0
        assert snap.circuit_breakers == 0
        assert snap.config_entries == 0
        assert snap.active_sessions == 0
        assert snap.registered_instances == 0

    def test_counts_after_inserts(self, conn):
        now = time.time()

        # Insert some data
        conn.execute(
            "INSERT INTO shared_memory (key, value, version, writer_role, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("k1", serialize("v1"), 1, "a", now),
        )
        conn.execute(
            "INSERT INTO circuit_state (tool_name, state, last_state_change) "
            "VALUES (?, ?, ?)",
            ("tool_a", "closed", now),
        )
        conn.execute(
            "INSERT INTO config_entries (namespace, key, value, version, config_type, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("ns", "k", serialize(True), 1, "feature_flag", now),
        )
        conn.execute(
            "INSERT INTO sessions (session_id, instance_id, state, payload, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("s1", "inst-1", "running", serialize({}), now, now),
        )
        conn.execute(
            "INSERT INTO sessions (session_id, instance_id, state, payload, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("s2", "inst-1", "completed", serialize({}), now, now),
        )
        # Register an alive instance
        conn.execute(
            "INSERT INTO instances (instance_id, hostname, started_at, last_heartbeat, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("inst-1", "host", now, now, "alive"),
        )
        conn.commit()

        tracker = StateTracker(conn)
        snap = tracker.snapshot()

        assert snap.shared_memory_keys == 1
        assert snap.circuit_breakers == 1
        assert snap.config_entries == 1
        assert snap.active_sessions == 1  # only "running", not "completed"
        assert snap.registered_instances == 1
        assert snap.alive_instances == 1
