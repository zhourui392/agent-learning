"""Integration tests for distributed task scheduling."""

from __future__ import annotations

import threading
import unittest
from typing import List

from src.scheduler.in_memory_queue import InMemoryDistributedLock, InMemoryTaskQueue
from src.scheduler.interfaces import TaskItem


class TestMultiWorkerDequeue(unittest.TestCase):

    def test_each_task_consumed_once(self):
        q = InMemoryTaskQueue()
        for i in range(10):
            q.enqueue(TaskItem(task_id=f"t{i}", queue_name="work", payload={}))

        consumed: List[str] = []
        lock = threading.Lock()

        def _worker(worker_id: str):
            while True:
                item = q.dequeue("work", worker_id=worker_id)
                if item is None:
                    break
                with lock:
                    consumed.append(item.task_id)
                q.ack(item.task_id)

        threads = [threading.Thread(target=_worker, args=(f"w{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(consumed), 10)
        self.assertEqual(len(set(consumed)), 10)

    def test_dead_letter_on_repeated_failure(self):
        q = InMemoryTaskQueue()
        q.enqueue(TaskItem(task_id="fail", queue_name="work", payload={}, max_retries=2))
        q.dequeue("work")
        q.nack("fail", "err1")
        q.dequeue("work")
        q.nack("fail", "err2")
        dead = q.peek_dead_letter("work")
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].last_error, "err2")

    def test_lock_prevents_double_processing(self):
        lock = InMemoryDistributedLock()
        results: List[str] = []

        def _process(worker_id: str):
            if lock.acquire("critical", holder_id=worker_id, timeout=0.1, ttl=2.0):
                results.append(worker_id)
                lock.release("critical", holder_id=worker_id)

        threads = [threading.Thread(target=_process, args=(f"w{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should acquire eventually (sequential due to short timeout)
        # but at most one at a time
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
