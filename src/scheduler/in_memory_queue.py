"""Threading-based in-memory task queue and distributed lock."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from src.scheduler.interfaces import DistributedLock, TaskItem, TaskQueue


class InMemoryTaskQueue(TaskQueue):
    """In-process task queue backed by a deque per queue name."""

    def __init__(self) -> None:
        self._queues: Dict[str, Deque[str]] = {}
        self._items: Dict[str, TaskItem] = {}
        self._dead_letter: Dict[str, List[TaskItem]] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def enqueue(self, item: TaskItem) -> TaskItem:
        with self._condition:
            item.status = "pending"
            self._items[item.task_id] = item
            self._queues.setdefault(item.queue_name, deque()).append(item.task_id)
            self._condition.notify_all()
        return item

    def dequeue(self, queue_name: str, worker_id: str = "") -> Optional[TaskItem]:
        with self._lock:
            q = self._queues.get(queue_name, deque())
            if not q:
                return None
            task_id = q.popleft()
            item = self._items[task_id]
            item.status = "processing"
            item.attempt_count += 1
            item.worker_id = worker_id
            return item

    def ack(self, task_id: str) -> bool:
        with self._lock:
            item = self._items.pop(task_id, None)
            if item is None:
                return False
            item.status = "completed"
            return True

    def nack(self, task_id: str, error: str = "") -> bool:
        with self._lock:
            item = self._items.get(task_id)
            if item is None:
                return False
            item.last_error = error
            if item.attempt_count >= item.max_retries:
                item.status = "dead"
                self._items.pop(task_id, None)
                self._dead_letter.setdefault(item.queue_name, []).append(item)
            else:
                item.status = "pending"
                self._queues.setdefault(item.queue_name, deque()).append(task_id)
            return True

    def peek_dead_letter(self, queue_name: str) -> List[TaskItem]:
        with self._lock:
            return list(self._dead_letter.get(queue_name, []))

    def queue_length(self, queue_name: str) -> int:
        with self._lock:
            return len(self._queues.get(queue_name, deque()))

    def close(self) -> None:
        with self._lock:
            self._queues.clear()
            self._items.clear()
            self._dead_letter.clear()


class InMemoryDistributedLock(DistributedLock):
    """In-process distributed lock backed by threading primitives."""

    def __init__(self) -> None:
        self._locks: Dict[str, Tuple[str, float]] = {}  # name -> (holder, expires_at)
        self._lock = threading.Lock()

    def acquire(
        self,
        lock_name: str,
        holder_id: str = "",
        timeout: float = 10.0,
        ttl: float = 30.0,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._cleanup_expired()
                if lock_name not in self._locks:
                    self._locks[lock_name] = (holder_id, time.monotonic() + ttl)
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def release(self, lock_name: str, holder_id: str = "") -> bool:
        with self._lock:
            entry = self._locks.get(lock_name)
            if entry is None:
                return False
            if holder_id and entry[0] != holder_id:
                return False
            del self._locks[lock_name]
            return True

    def is_locked(self, lock_name: str) -> bool:
        with self._lock:
            self._cleanup_expired()
            return lock_name in self._locks

    def _cleanup_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._locks.items() if now >= exp]
        for k in expired:
            del self._locks[k]
