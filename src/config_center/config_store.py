"""Configuration center -- namespace-aware CRUD with versioning and watch/notify."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from src.config_center.models import ConfigEntry, WatchEvent
from src.config_center.watcher import ConfigWatcher, WatchCallback
from src.persistence.in_memory import InMemoryConfigBackend
from src.persistence.interfaces import ConfigBackend, ConfigRecord


class ConfigCenter:
    """Unified configuration center with namespace, versioning, and watch.

    Parameters
    ----------
    backend : ConfigBackend, optional
        Persistence backend.  Defaults to in-memory.
    """

    def __init__(self, backend: Optional[ConfigBackend] = None) -> None:
        self._backend = backend or InMemoryConfigBackend()
        self._watcher = ConfigWatcher()

    # -- CRUD ---------------------------------------------------------------

    def get(self, namespace: str, key: str) -> Optional[ConfigEntry]:
        """Return the current entry or ``None``."""
        record = self._backend.get(namespace, key)
        if record is None:
            return None
        return self._record_to_entry(record)

    def put(
        self,
        namespace: str,
        key: str,
        value: Any,
        config_type: str = "feature_flag",
        description: str = "",
    ) -> ConfigEntry:
        """Create or update a config entry.  Version auto-increments."""
        existing = self._backend.get(namespace, key)
        old_value = existing.value if existing else None
        old_version = existing.version if existing else 0
        new_version = old_version + 1
        now = time.time()

        record = ConfigRecord(
            namespace=namespace,
            key=key,
            value=value,
            version=new_version,
            config_type=config_type,
            updated_at=now,
            description=description,
        )
        self._backend.put(record)

        # Notify watchers
        event_type = "created" if existing is None else "updated"
        event = WatchEvent(
            namespace=namespace,
            key=key,
            old_value=old_value,
            new_value=value,
            old_version=old_version,
            new_version=new_version,
            event_type=event_type,
        )
        self._watcher.notify(event)

        return self._record_to_entry(record)

    def delete(self, namespace: str, key: str) -> bool:
        """Delete an entry.  Notifies watchers with event_type='deleted'."""
        existing = self._backend.get(namespace, key)
        if existing is None:
            return False

        self._backend.delete(namespace, key)

        event = WatchEvent(
            namespace=namespace,
            key=key,
            old_value=existing.value,
            new_value=None,
            old_version=existing.version,
            new_version=existing.version,
            event_type="deleted",
        )
        self._watcher.notify(event)
        return True

    # -- Query --------------------------------------------------------------

    def list_namespace(self, namespace: str) -> List[ConfigEntry]:
        """Return all entries in a namespace."""
        return [self._record_to_entry(r) for r in self._backend.list_by_namespace(namespace)]

    def list_all(self) -> List[ConfigEntry]:
        """Return every config entry."""
        return [self._record_to_entry(r) for r in self._backend.list_all()]

    def history(self, namespace: str, key: str) -> List[ConfigEntry]:
        """Return version history for one key (oldest first)."""
        return [self._record_to_entry(r) for r in self._backend.get_history(namespace, key)]

    # -- Watch / Notify -----------------------------------------------------

    def watch(self, namespace: str, key: str, callback: WatchCallback) -> None:
        """Subscribe to changes on (namespace, key).  Use ``key='*'`` for all."""
        self._watcher.watch(namespace, key, callback)

    def unwatch(self, namespace: str, key: str, callback: WatchCallback) -> bool:
        """Remove a watch callback."""
        return self._watcher.unwatch(namespace, key, callback)

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _record_to_entry(record: ConfigRecord) -> ConfigEntry:
        return ConfigEntry(
            namespace=record.namespace,
            key=record.key,
            value=record.value,
            version=record.version,
            config_type=record.config_type,
            updated_at=record.updated_at,
            description=record.description,
        )
