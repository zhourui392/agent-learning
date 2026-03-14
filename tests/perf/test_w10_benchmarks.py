"""Performance benchmarks for W10 distributed infrastructure."""

from __future__ import annotations

import time
import unittest

from src.messaging.in_memory_bus import InMemoryMessageBus
from src.persistence.redis_backend import RedisSharedMemoryBackend
from src.persistence.interfaces import MemoryRecord
from src.scheduler.in_memory_queue import InMemoryTaskQueue
from src.scheduler.interfaces import TaskItem


class TestMessageBusThroughput(unittest.TestCase):

    def test_publish_throughput_1000(self):
        """1000 publishes should complete in < 1s."""
        bus = InMemoryMessageBus()
        count = 0
        bus.subscribe("bench", lambda m: None)

        start = time.monotonic()
        for i in range(1000):
            bus.publish("bench", {"i": i})
            count += 1
        elapsed = time.monotonic() - start

        bus.close()
        self.assertEqual(count, 1000)
        self.assertLess(elapsed, 1.0, f"Too slow: {elapsed:.3f}s")


class TestTaskQueueThroughput(unittest.TestCase):

    def test_enqueue_dequeue_1000(self):
        """1000 enqueue+dequeue cycles should complete in < 2s."""
        q = InMemoryTaskQueue()
        start = time.monotonic()
        for i in range(1000):
            q.enqueue(TaskItem(task_id=f"t{i}", queue_name="bench", payload={}))
        for i in range(1000):
            item = q.dequeue("bench")
            q.ack(item.task_id)
        elapsed = time.monotonic() - start
        q.close()
        self.assertLess(elapsed, 2.0, f"Too slow: {elapsed:.3f}s")


class TestRedisBackendThroughput(unittest.TestCase):

    def test_shared_memory_1000_ops(self):
        """1000 put+get cycles should complete in < 2s."""
        backend = RedisSharedMemoryBackend()
        backend.clear()
        start = time.monotonic()
        for i in range(1000):
            backend.put(MemoryRecord(
                key=f"k{i}", value=f"v{i}", version=1,
                writer_role="bench", updated_at=time.time(),
            ))
        for i in range(1000):
            backend.get(f"k{i}")
        elapsed = time.monotonic() - start
        backend.clear()
        self.assertLess(elapsed, 2.0, f"Too slow: {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
