"""W9 integration: persistence layer end-to-end."""

from __future__ import annotations

import sqlite3
import time

import pytest

from src.persistence.schema import SchemaManager
from src.persistence.sqlite_backend import (
    SQLiteCircuitStateBackend,
    SQLiteConfigBackend,
    SQLiteSessionStoreBackend,
    SQLiteSharedMemoryBackend,
)
from src.persistence.interfaces import (
    CircuitRecord,
    ConfigRecord,
    MemoryRecord,
    SessionRecord,
)
from src.multi_agent.shared_memory import SharedMemoryStore
from src.gateway.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    SchemaManager(c).ensure_schema()
    yield c
    c.close()


class TestSharedMemoryPersistence:
    """Write via SharedMemoryStore -> new instance reads same data."""

    def test_write_then_read_from_new_instance(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)

        store1 = SharedMemoryStore(backend=backend)
        store1.write("task_plan", {"steps": [1, 2, 3]}, writer_role="planner")

        # Simulate new process
        store2 = SharedMemoryStore(backend=backend)
        entry = store2.read("task_plan")
        assert entry is not None
        assert entry.value == {"steps": [1, 2, 3]}
        assert entry.version == 1

    def test_version_conflict_across_instances(self, conn):
        backend = SQLiteSharedMemoryBackend(conn)

        store1 = SharedMemoryStore(backend=backend)
        store1.write("k", "v1", writer_role="a")

        store2 = SharedMemoryStore(backend=backend)
        from src.multi_agent.shared_memory import VersionConflictError
        with pytest.raises(VersionConflictError):
            store2.write("k", "v2", writer_role="b", expected_version=0)


class TestCircuitBreakerPersistence:
    """Circuit state survives across instances."""

    def test_state_survives_restart(self, conn):
        backend = SQLiteCircuitStateBackend(conn)
        config = CircuitConfig(failure_threshold=3, recovery_timeout=5.0, success_threshold=2)

        cb1 = CircuitBreaker(config=config, backend=backend)
        for _ in range(3):
            cb1.record_failure("tool_x")
        assert cb1.get_state("tool_x") == CircuitState.OPEN

        # New instance loads from DB
        cb2 = CircuitBreaker(config=config, backend=backend)
        assert cb2.get_state("tool_x") == CircuitState.OPEN
        stats = cb2.get_stats("tool_x")
        assert stats.total_failures == 3


class TestAllBackendsTogether:
    """All four SQLite backends coexist in one database."""

    def test_multi_backend_coexistence(self, conn):
        sm = SQLiteSharedMemoryBackend(conn)
        cs = SQLiteCircuitStateBackend(conn)
        cf = SQLiteConfigBackend(conn)
        ss = SQLiteSessionStoreBackend(conn)

        now = time.time()
        sm.put(MemoryRecord(key="k", value="v", version=1, writer_role="a", updated_at=now))
        cs.put(CircuitRecord(tool_name="t", state="closed", failure_count=0, success_count=0,
                             half_open_successes=0, last_failure_time=0, last_state_change=now,
                             total_calls=0, total_failures=0, total_rejections=0))
        cf.put(ConfigRecord(namespace="ns", key="k", value=True, version=1,
                            config_type="feature_flag", updated_at=now))
        ss.put(SessionRecord(session_id="s1", instance_id="i1", state="running",
                             payload={}, created_at=now, updated_at=now))

        assert sm.get("k") is not None
        assert cs.get("t") is not None
        assert cf.get("ns", "k") is not None
        assert ss.get("s1") is not None
