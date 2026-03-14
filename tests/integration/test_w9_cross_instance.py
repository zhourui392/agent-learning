"""W9 integration: cross-instance recovery full pipeline."""

from __future__ import annotations

import sqlite3
import time

import pytest

from src.persistence.instance_registry import InstanceRegistry
from src.persistence.recovery import CrossInstanceRecovery
from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import SQLiteSessionStoreBackend
from src.persistence.state_tracker import StateTracker
from src.persistence.interfaces import SessionRecord


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestCrossInstanceFullPipeline:

    def test_crash_recovery_and_state_tracking(self, conn):
        """Simulate: inst-1 creates sessions, crashes, inst-2 recovers."""
        session_backend = SQLiteSessionStoreBackend(conn)
        registry = InstanceRegistry(conn, heartbeat_ttl=0.01)
        tracker = StateTracker(conn, heartbeat_ttl=0.01)

        # 1. inst-1 registers and creates sessions
        registry.register("inst-1", hostname="host-a")
        now = time.time()
        session_backend.put(SessionRecord(
            session_id="sess-1", instance_id="inst-1", state="running",
            payload={"step": "analyze"}, created_at=now, updated_at=now,
        ))
        session_backend.put(SessionRecord(
            session_id="sess-2", instance_id="inst-1", state="pending",
            payload={"step": "plan"}, created_at=now, updated_at=now,
        ))

        # 2. Verify initial state
        snap = tracker.snapshot()
        assert snap.active_sessions == 2
        assert snap.registered_instances == 1

        # 3. inst-1 crashes (heartbeat expires)
        time.sleep(0.02)

        # 4. inst-2 starts and runs recovery
        registry.register("inst-2", hostname="host-b")
        recovery = CrossInstanceRecovery(session_backend, registry, "inst-2")
        result = recovery.recover()

        assert "inst-1" in result.expired_instances
        assert len(result.recovered_sessions) == 2

        # 5. Verify state after recovery
        snap = tracker.snapshot()
        assert snap.registered_instances == 2
        assert snap.alive_instances == 1  # only inst-2

        s1 = session_backend.get("sess-1")
        assert s1.instance_id == "inst-2"
        assert s1.state == "recovered"

    def test_healthy_instance_no_recovery(self, conn):
        """No recovery needed when all instances are alive."""
        session_backend = SQLiteSessionStoreBackend(conn)
        registry = InstanceRegistry(conn, heartbeat_ttl=60.0)

        registry.register("inst-1")
        now = time.time()
        session_backend.put(SessionRecord(
            session_id="s1", instance_id="inst-1", state="running",
            payload={}, created_at=now, updated_at=now,
        ))

        recovery = CrossInstanceRecovery(session_backend, registry, "inst-2")
        result = recovery.recover()

        assert result.expired_instances == []
        assert result.recovered_sessions == []

        # Session unchanged
        assert session_backend.get("s1").state == "running"
