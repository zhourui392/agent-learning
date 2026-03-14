"""SQLite backend tests -- runs the same contract suite plus SQLite-specific tests."""

from __future__ import annotations

import sqlite3
import tempfile
import time

import pytest

from src.persistence.interfaces import (
    CircuitRecord,
    ConfigRecord,
    MemoryRecord,
    SessionRecord,
)
from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import (
    SQLiteCircuitStateBackend,
    SQLiteConfigBackend,
    SQLiteSessionStoreBackend,
    SQLiteSharedMemoryBackend,
)


@pytest.fixture
def conn():
    """In-memory SQLite with schema initialized."""
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


# ---------------------------------------------------------------------------
# SharedMemory
# ---------------------------------------------------------------------------

class TestSQLiteSharedMemory:

    def test_put_and_get(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)
        record = MemoryRecord(key="k1", value={"a": 1}, version=1, writer_role="p", updated_at=time.time())
        backend.put(record)
        got = backend.get("k1")
        assert got is not None
        assert got.value == {"a": 1}

    def test_overwrite(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)
        backend.put(MemoryRecord(key="k1", value="v1", version=1, writer_role="a", updated_at=time.time()))
        backend.put(MemoryRecord(key="k1", value="v2", version=2, writer_role="b", updated_at=time.time()))
        assert backend.get("k1").value == "v2"

    def test_delete(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)
        backend.put(MemoryRecord(key="k1", value="v", version=1, writer_role="a", updated_at=time.time()))
        assert backend.delete("k1") is True
        assert backend.get("k1") is None

    def test_list_and_clear(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)
        for i in range(3):
            backend.put(MemoryRecord(key=f"k{i}", value=i, version=1, writer_role="a", updated_at=time.time()))
        assert len(backend.list_all()) == 3
        backend.clear()
        assert backend.list_all() == []


# ---------------------------------------------------------------------------
# CircuitState
# ---------------------------------------------------------------------------

class TestSQLiteCircuitState:

    def _make(self, name: str = "tool_a") -> CircuitRecord:
        return CircuitRecord(
            tool_name=name, state="closed", failure_count=0, success_count=0,
            half_open_successes=0, last_failure_time=0.0, last_state_change=time.time(),
            total_calls=0, total_failures=0, total_rejections=0,
        )

    def test_put_and_get(self, conn):
        backend = SQLiteCircuitStateBackend(conn)
        backend.put(self._make())
        got = backend.get("tool_a")
        assert got is not None
        assert got.state == "closed"

    def test_list_and_clear(self, conn):
        backend = SQLiteCircuitStateBackend(conn)
        backend.put(self._make("a"))
        backend.put(self._make("b"))
        assert len(backend.list_all()) == 2
        backend.clear()
        assert backend.list_all() == []


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestSQLiteConfig:

    def _make(self, ns="default", key="k1", version=1) -> ConfigRecord:
        return ConfigRecord(
            namespace=ns, key=key, value={"flag": True}, version=version,
            config_type="feature_flag", updated_at=time.time(), description="test",
        )

    def test_put_and_get(self, conn):
        backend = SQLiteConfigBackend(conn)
        backend.put(self._make())
        got = backend.get("default", "k1")
        assert got is not None
        assert got.value == {"flag": True}

    def test_history(self, conn):
        backend = SQLiteConfigBackend(conn)
        backend.put(self._make(version=1))
        backend.put(self._make(version=2))
        history = backend.get_history("default", "k1")
        assert len(history) == 2
        assert history[0].version == 1

    def test_list_by_namespace(self, conn):
        backend = SQLiteConfigBackend(conn)
        backend.put(self._make("ns1", "a"))
        backend.put(self._make("ns1", "b"))
        backend.put(self._make("ns2", "c"))
        assert len(backend.list_by_namespace("ns1")) == 2


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TestSQLiteSessions:

    def _make(self, sid="s1", iid="inst-1", state="running") -> SessionRecord:
        now = time.time()
        return SessionRecord(
            session_id=sid, instance_id=iid, state=state,
            payload={"step": 1}, created_at=now, updated_at=now,
        )

    def test_put_and_get(self, conn):
        backend = SQLiteSessionStoreBackend(conn)
        backend.put(self._make())
        got = backend.get("s1")
        assert got is not None
        assert got.instance_id == "inst-1"

    def test_list_by_instance(self, conn):
        backend = SQLiteSessionStoreBackend(conn)
        backend.put(self._make("s1", "inst-1"))
        backend.put(self._make("s2", "inst-1"))
        backend.put(self._make("s3", "inst-2"))
        assert len(backend.list_by_instance("inst-1")) == 2

    def test_list_by_state(self, conn):
        backend = SQLiteSessionStoreBackend(conn)
        backend.put(self._make("s1", state="running"))
        backend.put(self._make("s2", state="completed"))
        assert len(backend.list_by_state("running")) == 1
