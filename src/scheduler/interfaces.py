"""Abstract task queue and distributed lock interfaces."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class TaskItem:
    """One item in a distributed task queue."""

    task_id: str
    queue_name: str
    payload: Any
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | processing | completed | dead
    attempt_count: int = 0
    max_retries: int = 3
    processing_timeout: float = 30.0
    last_error: Optional[str] = None
    worker_id: Optional[str] = None


class TaskQueue(ABC):
    """Distributed task queue contract."""

    @abstractmethod
    def enqueue(self, item: TaskItem) -> TaskItem:
        """Add an item to its queue."""

    @abstractmethod
    def dequeue(self, queue_name: str, worker_id: str = "") -> Optional[TaskItem]:
        """Pop the next pending item and mark it *processing*."""

    @abstractmethod
    def ack(self, task_id: str) -> bool:
        """Acknowledge successful processing.  Return ``True`` if found."""

    @abstractmethod
    def nack(self, task_id: str, error: str = "") -> bool:
        """Reject and re-queue (or move to dead-letter if retries exhausted)."""

    @abstractmethod
    def peek_dead_letter(self, queue_name: str) -> List[TaskItem]:
        """Return items in the dead-letter queue."""

    @abstractmethod
    def queue_length(self, queue_name: str) -> int:
        """Number of pending items in a queue."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


class DistributedLock(ABC):
    """Distributed locking contract."""

    @abstractmethod
    def acquire(
        self,
        lock_name: str,
        holder_id: str = "",
        timeout: float = 10.0,
        ttl: float = 30.0,
    ) -> bool:
        """Acquire a named lock.  Block up to *timeout* seconds."""

    @abstractmethod
    def release(self, lock_name: str, holder_id: str = "") -> bool:
        """Release a lock.  Return ``True`` if released by this holder."""

    @abstractmethod
    def is_locked(self, lock_name: str) -> bool:
        """Check whether a lock is currently held."""
