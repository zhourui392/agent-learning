"""Parameterized contract tests for persistence backends.

Every backend implementation (InMemory, SQLite) must pass the same suite.
"""

from __future__ import annotations

import time

import pytest

from src.persistence.in_memory import (
    InMemoryCircuitStateBackend,
    InMemoryConfigBackend,
    InMemorySessionStoreBackend,
    InMemorySharedMemoryBackend,
)
from src.persistence.interfaces import (
    CircuitRecord,
    ConfigRecord,
    MemoryRecord,
    SessionRecord,
)


# ---------------------------------------------------------------------------
# Fixtures -- one per backend type; will be extended for SQLite later
# ---------------------------------------------------------------------------

@pytest.fixture(params=["in_memory"])
def shared_memory_backend(request):
    if request.param == "in_memory":
        return InMemorySharedMemoryBackend()
    raise ValueError(request.param)


@pytest.fixture(params=["in_memory"])
def circuit_backend(request):
    if request.param == "in_memory":
        return InMemoryCircuitStateBackend()
    raise ValueError(request.param)


@pytest.fixture(params=["in_memory"])
def config_backend(request):
    if request.param == "in_memory":
        return InMemoryConfigBackend()
    raise ValueError(request.param)


@pytest.fixture(params=["in_memory"])
def session_backend(request):
    if request.param == "in_memory":
        return InMemorySessionStoreBackend()
    raise ValueError(request.param)


# ---------------------------------------------------------------------------
# SharedMemoryBackend contract
# ---------------------------------------------------------------------------

class TestSharedMemoryContract:

    def test_put_and_get(self, shared_memory_backend):
        record = MemoryRecord(
            key="k1", value={"a": 1}, version=1,
            writer_role="planner", updated_at=time.time(),
        )
        shared_memory_backend.put(record)
        got = shared_memory_backend.get("k1")

        assert got is not None
        assert got.key == "k1"
        assert got.value == {"a": 1}
        assert got.version == 1

    def test_get_missing_returns_none(self, shared_memory_backend):
        assert shared_memory_backend.get("missing") is None

    def test_put_overwrites(self, shared_memory_backend):
        r1 = MemoryRecord(key="k1", value="v1", version=1, writer_role="a", updated_at=time.time())
        r2 = MemoryRecord(key="k1", value="v2", version=2, writer_role="b", updated_at=time.time())
        shared_memory_backend.put(r1)
        shared_memory_backend.put(r2)

        got = shared_memory_backend.get("k1")
        assert got.value == "v2"
        assert got.version == 2

    def test_delete(self, shared_memory_backend):
        r = MemoryRecord(key="k1", value="v", version=1, writer_role="a", updated_at=time.time())
        shared_memory_backend.put(r)
        assert shared_memory_backend.delete("k1") is True
        assert shared_memory_backend.get("k1") is None

    def test_delete_missing(self, shared_memory_backend):
        assert shared_memory_backend.delete("nope") is False

    def test_list_all(self, shared_memory_backend):
        for i in range(3):
            shared_memory_backend.put(
                MemoryRecord(key=f"k{i}", value=i, version=1, writer_role="a", updated_at=time.time())
            )
        assert len(shared_memory_backend.list_all()) == 3

    def test_clear(self, shared_memory_backend):
        shared_memory_backend.put(
            MemoryRecord(key="k1", value="v", version=1, writer_role="a", updated_at=time.time())
        )
        shared_memory_backend.clear()
        assert shared_memory_backend.list_all() == []


# ---------------------------------------------------------------------------
# CircuitStateBackend contract
# ---------------------------------------------------------------------------

class TestCircuitStateContract:

    def _make_record(self, tool_name: str = "tool_a") -> CircuitRecord:
        return CircuitRecord(
            tool_name=tool_name, state="closed",
            failure_count=0, success_count=0, half_open_successes=0,
            last_failure_time=0.0, last_state_change=time.time(),
            total_calls=0, total_failures=0, total_rejections=0,
        )

    def test_put_and_get(self, circuit_backend):
        record = self._make_record()
        circuit_backend.put(record)
        got = circuit_backend.get("tool_a")
        assert got is not None
        assert got.tool_name == "tool_a"
        assert got.state == "closed"

    def test_get_missing(self, circuit_backend):
        assert circuit_backend.get("missing") is None

    def test_delete(self, circuit_backend):
        circuit_backend.put(self._make_record())
        assert circuit_backend.delete("tool_a") is True
        assert circuit_backend.get("tool_a") is None

    def test_list_all(self, circuit_backend):
        circuit_backend.put(self._make_record("a"))
        circuit_backend.put(self._make_record("b"))
        assert len(circuit_backend.list_all()) == 2

    def test_clear(self, circuit_backend):
        circuit_backend.put(self._make_record())
        circuit_backend.clear()
        assert circuit_backend.list_all() == []


# ---------------------------------------------------------------------------
# ConfigBackend contract
# ---------------------------------------------------------------------------

class TestConfigBackendContract:

    def _make_record(self, ns: str = "default", key: str = "k1", version: int = 1) -> ConfigRecord:
        return ConfigRecord(
            namespace=ns, key=key, value={"flag": True},
            version=version, config_type="feature_flag",
            updated_at=time.time(), description="test",
        )

    def test_put_and_get(self, config_backend):
        config_backend.put(self._make_record())
        got = config_backend.get("default", "k1")
        assert got is not None
        assert got.value == {"flag": True}

    def test_get_missing(self, config_backend):
        assert config_backend.get("ns", "missing") is None

    def test_delete(self, config_backend):
        config_backend.put(self._make_record())
        assert config_backend.delete("default", "k1") is True
        assert config_backend.get("default", "k1") is None

    def test_list_by_namespace(self, config_backend):
        config_backend.put(self._make_record("ns1", "a"))
        config_backend.put(self._make_record("ns1", "b"))
        config_backend.put(self._make_record("ns2", "c"))
        assert len(config_backend.list_by_namespace("ns1")) == 2

    def test_history(self, config_backend):
        config_backend.put(self._make_record(version=1))
        config_backend.put(self._make_record(version=2))
        history = config_backend.get_history("default", "k1")
        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].version == 2

    def test_clear(self, config_backend):
        config_backend.put(self._make_record())
        config_backend.clear()
        assert config_backend.list_all() == []


# ---------------------------------------------------------------------------
# SessionStoreBackend contract
# ---------------------------------------------------------------------------

class TestSessionStoreContract:

    def _make_record(self, sid: str = "s1", iid: str = "inst-1", state: str = "running") -> SessionRecord:
        now = time.time()
        return SessionRecord(
            session_id=sid, instance_id=iid, state=state,
            payload={"step": 1}, created_at=now, updated_at=now,
        )

    def test_put_and_get(self, session_backend):
        session_backend.put(self._make_record())
        got = session_backend.get("s1")
        assert got is not None
        assert got.instance_id == "inst-1"

    def test_get_missing(self, session_backend):
        assert session_backend.get("missing") is None

    def test_delete(self, session_backend):
        session_backend.put(self._make_record())
        assert session_backend.delete("s1") is True
        assert session_backend.get("s1") is None

    def test_list_by_instance(self, session_backend):
        session_backend.put(self._make_record("s1", "inst-1"))
        session_backend.put(self._make_record("s2", "inst-1"))
        session_backend.put(self._make_record("s3", "inst-2"))
        assert len(session_backend.list_by_instance("inst-1")) == 2

    def test_list_by_state(self, session_backend):
        session_backend.put(self._make_record("s1", state="running"))
        session_backend.put(self._make_record("s2", state="completed"))
        assert len(session_backend.list_by_state("running")) == 1

    def test_clear(self, session_backend):
        session_backend.put(self._make_record())
        session_backend.clear()
        assert session_backend.list_all() == []
