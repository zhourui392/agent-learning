"""In-memory implementations of persistence backends.

These adapters wrap plain dicts and lists so that existing code can keep
working with zero configuration while still honouring the backend ABCs.
"""

from __future__ import annotations

import copy
from typing import Dict, List, Optional

from src.persistence.interfaces import (
    CircuitRecord,
    CircuitStateBackend,
    ConfigBackend,
    ConfigRecord,
    MemoryRecord,
    SessionRecord,
    SessionStoreBackend,
    SharedMemoryBackend,
)


class InMemorySharedMemoryBackend(SharedMemoryBackend):
    """Dict-backed shared memory."""

    def __init__(self) -> None:
        self._store: Dict[str, MemoryRecord] = {}

    def get(self, key: str) -> Optional[MemoryRecord]:
        record = self._store.get(key)
        return copy.deepcopy(record) if record else None

    def put(self, record: MemoryRecord) -> None:
        self._store[record.key] = copy.deepcopy(record)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def list_all(self) -> List[MemoryRecord]:
        return [copy.deepcopy(r) for r in self._store.values()]

    def clear(self) -> None:
        self._store.clear()


class InMemoryCircuitStateBackend(CircuitStateBackend):
    """Dict-backed circuit state."""

    def __init__(self) -> None:
        self._store: Dict[str, CircuitRecord] = {}

    def get(self, tool_name: str) -> Optional[CircuitRecord]:
        record = self._store.get(tool_name)
        return copy.deepcopy(record) if record else None

    def put(self, record: CircuitRecord) -> None:
        self._store[record.tool_name] = copy.deepcopy(record)

    def delete(self, tool_name: str) -> bool:
        if tool_name in self._store:
            del self._store[tool_name]
            return True
        return False

    def list_all(self) -> List[CircuitRecord]:
        return [copy.deepcopy(r) for r in self._store.values()]

    def clear(self) -> None:
        self._store.clear()


class InMemoryConfigBackend(ConfigBackend):
    """Dict-backed configuration store with history."""

    def __init__(self) -> None:
        self._store: Dict[str, ConfigRecord] = {}
        self._history: Dict[str, List[ConfigRecord]] = {}

    @staticmethod
    def _composite_key(namespace: str, key: str) -> str:
        return f"{namespace}::{key}"

    def get(self, namespace: str, key: str) -> Optional[ConfigRecord]:
        record = self._store.get(self._composite_key(namespace, key))
        return copy.deepcopy(record) if record else None

    def put(self, record: ConfigRecord) -> None:
        ck = self._composite_key(record.namespace, record.key)
        self._store[ck] = copy.deepcopy(record)
        history = self._history.setdefault(ck, [])
        history.append(copy.deepcopy(record))

    def delete(self, namespace: str, key: str) -> bool:
        ck = self._composite_key(namespace, key)
        if ck in self._store:
            del self._store[ck]
            return True
        return False

    def list_by_namespace(self, namespace: str) -> List[ConfigRecord]:
        return [
            copy.deepcopy(r) for r in self._store.values()
            if r.namespace == namespace
        ]

    def list_all(self) -> List[ConfigRecord]:
        return [copy.deepcopy(r) for r in self._store.values()]

    def get_history(self, namespace: str, key: str) -> List[ConfigRecord]:
        ck = self._composite_key(namespace, key)
        return [copy.deepcopy(r) for r in self._history.get(ck, [])]

    def clear(self) -> None:
        self._store.clear()
        self._history.clear()


class InMemorySessionStoreBackend(SessionStoreBackend):
    """Dict-backed session store."""

    def __init__(self) -> None:
        self._store: Dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> Optional[SessionRecord]:
        record = self._store.get(session_id)
        return copy.deepcopy(record) if record else None

    def put(self, record: SessionRecord) -> None:
        self._store[record.session_id] = copy.deepcopy(record)

    def delete(self, session_id: str) -> bool:
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    def list_all(self) -> List[SessionRecord]:
        return [copy.deepcopy(r) for r in self._store.values()]

    def list_by_instance(self, instance_id: str) -> List[SessionRecord]:
        return [
            copy.deepcopy(r) for r in self._store.values()
            if r.instance_id == instance_id
        ]

    def list_by_state(self, state: str) -> List[SessionRecord]:
        return [
            copy.deepcopy(r) for r in self._store.values()
            if r.state == state
        ]

    def clear(self) -> None:
        self._store.clear()
