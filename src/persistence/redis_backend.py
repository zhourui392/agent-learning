"""Redis-backed persistence backends using fakeredis."""

from __future__ import annotations

import json
from typing import Any, List, Optional

try:
    import fakeredis
except ImportError:  # pragma: no cover
    fakeredis = None  # type: ignore[assignment]

from src.persistence.interfaces import (
    CircuitRecord,
    CircuitStateBackend,
    MemoryRecord,
    SharedMemoryBackend,
)


def _serialize(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _deserialize(raw: Any) -> Any:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


class RedisSharedMemoryBackend(SharedMemoryBackend):
    """Shared memory backend using Redis hashes (fakeredis)."""

    HASH_KEY = "agent:shared_memory"

    def __init__(self, redis_client: Optional[Any] = None, server: Optional[Any] = None) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = fakeredis.FakeRedis(server=server) if server else fakeredis.FakeRedis()

    def get(self, key: str) -> Optional[MemoryRecord]:
        raw = self._redis.hget(self.HASH_KEY, key)
        if raw is None:
            return None
        data = _deserialize(raw)
        return MemoryRecord(**data)

    def put(self, record: MemoryRecord) -> None:
        data = {
            "key": record.key,
            "value": record.value,
            "version": record.version,
            "writer_role": record.writer_role,
            "updated_at": record.updated_at,
            "expires_at": record.expires_at,
        }
        self._redis.hset(self.HASH_KEY, record.key, _serialize(data))

    def delete(self, key: str) -> bool:
        return self._redis.hdel(self.HASH_KEY, key) > 0

    def list_all(self) -> List[MemoryRecord]:
        all_data = self._redis.hgetall(self.HASH_KEY)
        return [MemoryRecord(**_deserialize(v)) for v in all_data.values()]

    def clear(self) -> None:
        self._redis.delete(self.HASH_KEY)


class RedisCircuitStateBackend(CircuitStateBackend):
    """Circuit state backend using Redis hashes (fakeredis)."""

    HASH_KEY = "agent:circuit_state"

    def __init__(self, redis_client: Optional[Any] = None, server: Optional[Any] = None) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = fakeredis.FakeRedis(server=server) if server else fakeredis.FakeRedis()

    def get(self, tool_name: str) -> Optional[CircuitRecord]:
        raw = self._redis.hget(self.HASH_KEY, tool_name)
        if raw is None:
            return None
        data = _deserialize(raw)
        return CircuitRecord(**data)

    def put(self, record: CircuitRecord) -> None:
        data = {
            "tool_name": record.tool_name,
            "state": record.state,
            "failure_count": record.failure_count,
            "success_count": record.success_count,
            "half_open_successes": record.half_open_successes,
            "last_failure_time": record.last_failure_time,
            "last_state_change": record.last_state_change,
            "total_calls": record.total_calls,
            "total_failures": record.total_failures,
            "total_rejections": record.total_rejections,
        }
        self._redis.hset(self.HASH_KEY, record.tool_name, _serialize(data))

    def delete(self, tool_name: str) -> bool:
        return self._redis.hdel(self.HASH_KEY, tool_name) > 0

    def list_all(self) -> List[CircuitRecord]:
        all_data = self._redis.hgetall(self.HASH_KEY)
        return [CircuitRecord(**_deserialize(v)) for v in all_data.values()]

    def clear(self) -> None:
        self._redis.delete(self.HASH_KEY)
