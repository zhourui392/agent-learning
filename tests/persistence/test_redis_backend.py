"""Contract tests for Redis persistence backends."""

from __future__ import annotations

import time
import unittest

from src.persistence.interfaces import CircuitRecord, MemoryRecord
from src.persistence.redis_backend import RedisCircuitStateBackend, RedisSharedMemoryBackend


class TestRedisSharedMemoryBackend(unittest.TestCase):

    def setUp(self):
        self.backend = RedisSharedMemoryBackend()
        self.backend.clear()

    def test_put_get(self):
        record = MemoryRecord(key="k1", value="v1", version=1, writer_role="agent", updated_at=time.time())
        self.backend.put(record)
        got = self.backend.get("k1")
        self.assertIsNotNone(got)
        self.assertEqual(got.key, "k1")
        self.assertEqual(got.value, "v1")

    def test_get_missing(self):
        self.assertIsNone(self.backend.get("nonexistent"))

    def test_delete(self):
        self.backend.put(MemoryRecord(key="k2", value="v2", version=1, writer_role="a", updated_at=time.time()))
        self.assertTrue(self.backend.delete("k2"))
        self.assertFalse(self.backend.delete("k2"))

    def test_list_all(self):
        self.backend.put(MemoryRecord(key="a", value=1, version=1, writer_role="x", updated_at=time.time()))
        self.backend.put(MemoryRecord(key="b", value=2, version=1, writer_role="x", updated_at=time.time()))
        self.assertEqual(len(self.backend.list_all()), 2)

    def test_clear(self):
        self.backend.put(MemoryRecord(key="c", value=3, version=1, writer_role="x", updated_at=time.time()))
        self.backend.clear()
        self.assertEqual(len(self.backend.list_all()), 0)


class TestRedisCircuitStateBackend(unittest.TestCase):

    def setUp(self):
        self.backend = RedisCircuitStateBackend()
        self.backend.clear()

    def _make_record(self, tool: str = "tool1") -> CircuitRecord:
        return CircuitRecord(
            tool_name=tool, state="closed", failure_count=0,
            success_count=0, half_open_successes=0,
            last_failure_time=0.0, last_state_change=time.time(),
            total_calls=10, total_failures=1, total_rejections=0,
        )

    def test_put_get(self):
        self.backend.put(self._make_record())
        got = self.backend.get("tool1")
        self.assertIsNotNone(got)
        self.assertEqual(got.tool_name, "tool1")
        self.assertEqual(got.state, "closed")

    def test_delete(self):
        self.backend.put(self._make_record("t2"))
        self.assertTrue(self.backend.delete("t2"))
        self.assertIsNone(self.backend.get("t2"))

    def test_list_all(self):
        self.backend.put(self._make_record("a"))
        self.backend.put(self._make_record("b"))
        self.assertEqual(len(self.backend.list_all()), 2)


if __name__ == "__main__":
    unittest.main()
