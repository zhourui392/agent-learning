"""Tests for cross-instance recovery."""

from __future__ import annotations

import sqlite3
import time

import pytest

from src.persistence.in_memory import InMemorySessionStoreBackend
from src.persistence.instance_registry import InstanceRegistry
from src.persistence.interfaces import SessionRecord
from src.persistence.recovery import CrossInstanceRecovery
from src.persistence.schema import SchemaManager


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestCrossInstanceRecovery:

    def test_recover_orphan_sessions(self, conn):
        session_backend = InMemorySessionStoreBackend()
        registry = InstanceRegistry(conn, heartbeat_ttl=0.01)

        # Instance-1 registers and creates sessions
        registry.register("inst-1")
        now = time.time()
        session_backend.put(SessionRecord(
            session_id="s1", instance_id="inst-1", state="running",
            payload={"task": "a"}, created_at=now, updated_at=now,
        ))
        session_backend.put(SessionRecord(
            session_id="s2", instance_id="inst-1", state="running",
            payload={"task": "b"}, created_at=now, updated_at=now,
        ))
        # One completed session should not be recovered
        session_backend.put(SessionRecord(
            session_id="s3", instance_id="inst-1", state="completed",
            payload={"task": "c"}, created_at=now, updated_at=now,
        ))

        # Simulate inst-1 dying
        time.sleep(0.02)

        # New instance recovers
        recovery = CrossInstanceRecovery(session_backend, registry, "inst-2")
        result = recovery.recover()

        assert "inst-1" in result.expired_instances
        assert set(result.orphan_sessions) == {"s1", "s2"}
        assert set(result.recovered_sessions) == {"s1", "s2"}

        # Verify sessions now owned by inst-2
        s1 = session_backend.get("s1")
        assert s1.instance_id == "inst-2"
        assert s1.state == "recovered"

        # Completed session unchanged
        s3 = session_backend.get("s3")
        assert s3.instance_id == "inst-1"
        assert s3.state == "completed"

    def test_no_orphans(self, conn):
        session_backend = InMemorySessionStoreBackend()
        registry = InstanceRegistry(conn, heartbeat_ttl=60.0)
        registry.register("inst-1")

        recovery = CrossInstanceRecovery(session_backend, registry, "inst-2")
        result = recovery.recover()

        assert result.expired_instances == []
        assert result.orphan_sessions == []
        assert result.recovered_sessions == []
