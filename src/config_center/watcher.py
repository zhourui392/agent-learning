"""Watch / notify mechanism for config changes."""

from __future__ import annotations

from typing import Callable, Dict, List

from src.config_center.models import WatchEvent

WatchCallback = Callable[[WatchEvent], None]


class ConfigWatcher:
    """Manage watch subscriptions and dispatch change events.

    Watchers can subscribe to:
    - A specific ``(namespace, key)`` pair
    - All keys in a namespace via ``(namespace, "*")``
    """

    def __init__(self) -> None:
        self._watchers: Dict[str, List[WatchCallback]] = {}

    @staticmethod
    def _watch_key(namespace: str, key: str) -> str:
        return f"{namespace}::{key}"

    def watch(self, namespace: str, key: str, callback: WatchCallback) -> None:
        """Register a callback for changes to *namespace/key*."""
        wk = self._watch_key(namespace, key)
        self._watchers.setdefault(wk, []).append(callback)

    def unwatch(self, namespace: str, key: str, callback: WatchCallback) -> bool:
        """Remove a specific callback.  Return ``True`` if it was found."""
        wk = self._watch_key(namespace, key)
        callbacks = self._watchers.get(wk, [])
        if callback in callbacks:
            callbacks.remove(callback)
            return True
        return False

    def notify(self, event: WatchEvent) -> int:
        """Dispatch *event* to matching watchers.  Return callback count."""
        count = 0

        # 1. Exact match
        exact_key = self._watch_key(event.namespace, event.key)
        for cb in self._watchers.get(exact_key, []):
            cb(event)
            count += 1

        # 2. Wildcard match
        wildcard_key = self._watch_key(event.namespace, "*")
        for cb in self._watchers.get(wildcard_key, []):
            cb(event)
            count += 1

        return count

    def watcher_count(self) -> int:
        """Total number of registered callbacks."""
        return sum(len(cbs) for cbs in self._watchers.values())

    def clear(self) -> None:
        """Remove all watchers."""
        self._watchers.clear()
