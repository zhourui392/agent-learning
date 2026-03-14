"""Versioned shared memory for W7 multi-agent collaboration.

W9 update: constructor accepts an optional ``SharedMemoryBackend`` for
persistent storage.  Defaults to in-memory when no backend is supplied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.persistence.interfaces import MemoryRecord, SharedMemoryBackend


class VersionConflictError(RuntimeError):
    """Raised when optimistic locking detects a version conflict."""


@dataclass
class MemoryEntry:
    """One shared memory cell."""

    key: str
    value: Any
    version: int
    writer_role: str
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None


class SharedMemoryStore:
    """Shared memory with optimistic concurrency control.

    Parameters
    ----------
    backend : SharedMemoryBackend, optional
        Persistence backend.  When ``None`` a private in-memory dict is used,
        preserving the original W7 behaviour.
    """

    def __init__(self, backend: Optional[SharedMemoryBackend] = None) -> None:
        self._backend = backend
        # Fast path: when no backend is given, keep the original dict-based path
        self._entries: Dict[str, MemoryEntry] = {}
        self._history: Dict[str, List[int]] = {}

    # -- helpers to bridge backend / local dict ---

    def _load(self, key: str) -> Optional[MemoryEntry]:
        if self._backend is not None:
            rec = self._backend.get(key)
            if rec is None:
                return None
            return MemoryEntry(
                key=rec.key, value=rec.value, version=rec.version,
                writer_role=rec.writer_role, updated_at=rec.updated_at,
                expires_at=rec.expires_at,
            )
        return self._entries.get(key)

    def _store(self, entry: MemoryEntry) -> None:
        if self._backend is not None:
            self._backend.put(MemoryRecord(
                key=entry.key, value=entry.value, version=entry.version,
                writer_role=entry.writer_role, updated_at=entry.updated_at,
                expires_at=entry.expires_at,
            ))
        else:
            self._entries[entry.key] = entry

    def _remove(self, key: str) -> None:
        if self._backend is not None:
            self._backend.delete(key)
        else:
            self._entries.pop(key, None)

    def _all_entries(self) -> Dict[str, MemoryEntry]:
        if self._backend is not None:
            return {
                rec.key: MemoryEntry(
                    key=rec.key, value=rec.value, version=rec.version,
                    writer_role=rec.writer_role, updated_at=rec.updated_at,
                    expires_at=rec.expires_at,
                )
                for rec in self._backend.list_all()
            }
        return dict(self._entries)

    # -- public API (unchanged signatures) ---

    def read(self, key: str) -> Optional[MemoryEntry]:
        """Read one memory entry if not expired."""

        self.cleanup_expired()
        entry = self._load(key)
        return None if entry is None else self._clone(entry)

    def write(
        self,
        key: str,
        value: Any,
        writer_role: str,
        expected_version: Optional[int] = None,
        ttl_seconds: Optional[float] = None,
    ) -> MemoryEntry:
        """Write one memory entry with optional optimistic version check."""

        self.cleanup_expired()
        current = self._load(key)
        if expected_version is not None:
            current_version = 0 if current is None else current.version
            if current_version != expected_version:
                raise VersionConflictError(
                    f"version conflict for '{key}': expected {expected_version}, actual {current_version}"
                )
        next_version = 1 if current is None else current.version + 1
        expires_at = None if ttl_seconds is None else time.time() + ttl_seconds
        entry = MemoryEntry(
            key=key,
            value=value,
            version=next_version,
            writer_role=writer_role,
            expires_at=expires_at,
        )
        self._store(entry)
        history = self._history.setdefault(key, [])
        history.append(next_version)
        return self._clone(entry)

    def cleanup_expired(self) -> List[str]:
        """Delete expired keys and return removed key names."""

        current_time = time.time()
        removed_keys: List[str] = []
        for key, entry in list(self._all_entries().items()):
            if entry.expires_at is None:
                continue
            if entry.expires_at > current_time:
                continue
            self._remove(key)
            removed_keys.append(key)
        return removed_keys

    def snapshot(self) -> Dict[str, MemoryEntry]:
        """Return a clone of current memory state."""

        self.cleanup_expired()
        return {key: self._clone(entry) for key, entry in self._all_entries().items()}

    def get_history(self, key: str) -> List[int]:
        """Return version history for one key."""

        return list(self._history.get(key, []))

    def _clone(self, entry: MemoryEntry) -> MemoryEntry:
        return MemoryEntry(
            key=entry.key,
            value=entry.value,
            version=entry.version,
            writer_role=entry.writer_role,
            updated_at=entry.updated_at,
            expires_at=entry.expires_at,
        )
