"""Connection pool abstractions for persistence backends."""

from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

try:
    import fakeredis
except ImportError:  # pragma: no cover
    fakeredis = None  # type: ignore[assignment]


class ConnectionPool(ABC):
    """Abstract connection pool."""

    @abstractmethod
    def get_connection(self) -> Any:
        """Borrow a connection from the pool."""

    @abstractmethod
    def release_connection(self, conn: Any) -> None:
        """Return a connection to the pool."""

    @abstractmethod
    def close_all(self) -> None:
        """Close every connection in the pool."""

    @abstractmethod
    def pool_size(self) -> int:
        """Current number of connections (busy + idle)."""


class RedisConnectionPool(ConnectionPool):
    """Connection pool backed by fakeredis instances sharing one FakeServer."""

    def __init__(self, max_connections: int = 10, server: Optional[Any] = None) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        self._server = server or fakeredis.FakeServer()
        self._max = max_connections
        self._idle: queue.Queue[Any] = queue.Queue()
        self._created = 0
        self._lock = threading.Lock()

    def get_connection(self) -> Any:
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            if self._created < self._max:
                self._created += 1
                return fakeredis.FakeRedis(server=self._server)
        return self._idle.get(timeout=5.0)

    def release_connection(self, conn: Any) -> None:
        self._idle.put(conn)

    def close_all(self) -> None:
        while not self._idle.empty():
            try:
                self._idle.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._created = 0

    def pool_size(self) -> int:
        with self._lock:
            return self._created
