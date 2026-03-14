"""Abstract backend interfaces for stateful components.

Each ABC defines the contract that both InMemory and SQLite backends must
satisfy.  All methods are synchronous -- async wrappers live elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Shared Memory Backend
# ---------------------------------------------------------------------------

@dataclass
class MemoryRecord:
    """Flat persistence record for one shared-memory cell."""

    key: str
    value: Any
    version: int
    writer_role: str
    updated_at: float
    expires_at: Optional[float] = None


class SharedMemoryBackend(ABC):
    """Persist versioned shared-memory entries."""

    @abstractmethod
    def get(self, key: str) -> Optional[MemoryRecord]:
        """Return the current record or ``None``."""

    @abstractmethod
    def put(self, record: MemoryRecord) -> None:
        """Upsert one record (caller already resolved version)."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete one key.  Return ``True`` if it existed."""

    @abstractmethod
    def list_all(self) -> List[MemoryRecord]:
        """Return every stored record (no expiry filtering)."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all records."""


# ---------------------------------------------------------------------------
# Circuit State Backend
# ---------------------------------------------------------------------------

@dataclass
class CircuitRecord:
    """Flat persistence record for one circuit breaker."""

    tool_name: str
    state: str
    failure_count: int
    success_count: int
    half_open_successes: int
    last_failure_time: float
    last_state_change: float
    total_calls: int
    total_failures: int
    total_rejections: int


class CircuitStateBackend(ABC):
    """Persist per-tool circuit breaker state."""

    @abstractmethod
    def get(self, tool_name: str) -> Optional[CircuitRecord]:
        """Return the circuit record or ``None``."""

    @abstractmethod
    def put(self, record: CircuitRecord) -> None:
        """Upsert one circuit record."""

    @abstractmethod
    def delete(self, tool_name: str) -> bool:
        """Delete one circuit.  Return ``True`` if it existed."""

    @abstractmethod
    def list_all(self) -> List[CircuitRecord]:
        """Return every circuit record."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all circuit records."""


# ---------------------------------------------------------------------------
# Config Backend
# ---------------------------------------------------------------------------

@dataclass
class ConfigRecord:
    """Flat persistence record for one configuration entry."""

    namespace: str
    key: str
    value: Any
    version: int
    config_type: str
    updated_at: float
    description: str = ""


class ConfigBackend(ABC):
    """Persist configuration entries with namespace and versioning."""

    @abstractmethod
    def get(self, namespace: str, key: str) -> Optional[ConfigRecord]:
        """Return the current config record or ``None``."""

    @abstractmethod
    def put(self, record: ConfigRecord) -> None:
        """Upsert one config record."""

    @abstractmethod
    def delete(self, namespace: str, key: str) -> bool:
        """Delete one config entry.  Return ``True`` if it existed."""

    @abstractmethod
    def list_by_namespace(self, namespace: str) -> List[ConfigRecord]:
        """Return all entries in a namespace."""

    @abstractmethod
    def list_all(self) -> List[ConfigRecord]:
        """Return every config record."""

    @abstractmethod
    def get_history(self, namespace: str, key: str) -> List[ConfigRecord]:
        """Return version history for one key (oldest first)."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all config records."""


# ---------------------------------------------------------------------------
# Session Store Backend
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    """Flat persistence record for one session."""

    session_id: str
    instance_id: str
    state: str
    payload: Any
    created_at: float
    updated_at: float
    expires_at: Optional[float] = None


class SessionStoreBackend(ABC):
    """Persist session state for cross-instance recovery."""

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionRecord]:
        """Return the session record or ``None``."""

    @abstractmethod
    def put(self, record: SessionRecord) -> None:
        """Upsert one session record."""

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete one session.  Return ``True`` if it existed."""

    @abstractmethod
    def list_all(self) -> List[SessionRecord]:
        """Return every session record."""

    @abstractmethod
    def list_by_instance(self, instance_id: str) -> List[SessionRecord]:
        """Return all sessions owned by an instance."""

    @abstractmethod
    def list_by_state(self, state: str) -> List[SessionRecord]:
        """Return all sessions in a given state."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all session records."""
