"""Redis-backed task queue and distributed lock using fakeredis."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

try:
    import fakeredis
except ImportError:  # pragma: no cover
    fakeredis = None  # type: ignore[assignment]

from src.scheduler.interfaces import DistributedLock, TaskItem, TaskQueue


def _task_to_dict(item: TaskItem) -> Dict[str, Any]:
    return {
        "task_id": item.task_id,
        "queue_name": item.queue_name,
        "payload": item.payload,
        "priority": item.priority,
        "created_at": item.created_at,
        "status": item.status,
        "attempt_count": item.attempt_count,
        "max_retries": item.max_retries,
        "processing_timeout": item.processing_timeout,
        "last_error": item.last_error,
        "worker_id": item.worker_id,
    }


def _dict_to_task(data: Dict[str, Any]) -> TaskItem:
    return TaskItem(**data)


class RedisTaskQueue(TaskQueue):
    """Task queue backed by Redis lists and hashes (fakeredis)."""

    QUEUE_PREFIX = "tq:queue:"
    ITEM_PREFIX = "tq:item:"
    DEAD_PREFIX = "tq:dead:"

    def __init__(self, redis_client: Optional[Any] = None, server: Optional[Any] = None) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = fakeredis.FakeRedis(server=server) if server else fakeredis.FakeRedis()

    def enqueue(self, item: TaskItem) -> TaskItem:
        item.status = "pending"
        self._redis.set(
            f"{self.ITEM_PREFIX}{item.task_id}",
            json.dumps(_task_to_dict(item)),
        )
        self._redis.rpush(f"{self.QUEUE_PREFIX}{item.queue_name}", item.task_id)
        return item

    def dequeue(self, queue_name: str, worker_id: str = "") -> Optional[TaskItem]:
        task_id = self._redis.lpop(f"{self.QUEUE_PREFIX}{queue_name}")
        if task_id is None:
            return None
        if isinstance(task_id, bytes):
            task_id = task_id.decode("utf-8")
        raw = self._redis.get(f"{self.ITEM_PREFIX}{task_id}")
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        item = _dict_to_task(json.loads(raw))
        item.status = "processing"
        item.attempt_count += 1
        item.worker_id = worker_id
        self._redis.set(f"{self.ITEM_PREFIX}{task_id}", json.dumps(_task_to_dict(item)))
        return item

    def ack(self, task_id: str) -> bool:
        key = f"{self.ITEM_PREFIX}{task_id}"
        raw = self._redis.get(key)
        if raw is None:
            return False
        self._redis.delete(key)
        return True

    def nack(self, task_id: str, error: str = "") -> bool:
        key = f"{self.ITEM_PREFIX}{task_id}"
        raw = self._redis.get(key)
        if raw is None:
            return False
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        item = _dict_to_task(json.loads(raw))
        item.last_error = error
        if item.attempt_count >= item.max_retries:
            item.status = "dead"
            self._redis.delete(key)
            self._redis.rpush(
                f"{self.DEAD_PREFIX}{item.queue_name}",
                json.dumps(_task_to_dict(item)),
            )
        else:
            item.status = "pending"
            self._redis.set(key, json.dumps(_task_to_dict(item)))
            self._redis.rpush(f"{self.QUEUE_PREFIX}{item.queue_name}", task_id)
        return True

    def peek_dead_letter(self, queue_name: str) -> List[TaskItem]:
        dead_key = f"{self.DEAD_PREFIX}{queue_name}"
        raw_items = self._redis.lrange(dead_key, 0, -1)
        result = []
        for raw in raw_items:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            result.append(_dict_to_task(json.loads(raw)))
        return result

    def queue_length(self, queue_name: str) -> int:
        return self._redis.llen(f"{self.QUEUE_PREFIX}{queue_name}")

    def close(self) -> None:
        self._redis.flushdb()


class RedisDistributedLock(DistributedLock):
    """Distributed lock backed by Redis SET NX EX (fakeredis)."""

    LOCK_PREFIX = "lock:"

    def __init__(self, redis_client: Optional[Any] = None, server: Optional[Any] = None) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = fakeredis.FakeRedis(server=server) if server else fakeredis.FakeRedis()

    def acquire(
        self,
        lock_name: str,
        holder_id: str = "",
        timeout: float = 10.0,
        ttl: float = 30.0,
    ) -> bool:
        key = f"{self.LOCK_PREFIX}{lock_name}"
        deadline = time.monotonic() + timeout
        ttl_ms = int(ttl * 1000)
        while True:
            result = self._redis.set(key, holder_id or "_", nx=True, px=ttl_ms)
            if result:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def release(self, lock_name: str, holder_id: str = "") -> bool:
        key = f"{self.LOCK_PREFIX}{lock_name}"
        if holder_id:
            current = self._redis.get(key)
            if current is None:
                return False
            if isinstance(current, bytes):
                current = current.decode("utf-8")
            if current != holder_id:
                return False
        return bool(self._redis.delete(key))

    def is_locked(self, lock_name: str) -> bool:
        return self._redis.exists(f"{self.LOCK_PREFIX}{lock_name}") > 0
