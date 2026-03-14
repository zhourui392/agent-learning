"""Contract tests for TaskQueue implementations."""

from __future__ import annotations

import unittest

from src.scheduler.interfaces import TaskItem
from src.scheduler.in_memory_queue import InMemoryTaskQueue

try:
    from src.scheduler.redis_queue import RedisTaskQueue
    HAS_FAKEREDIS = True
except RuntimeError:
    HAS_FAKEREDIS = False


def _create_queues():
    yield "in_memory", InMemoryTaskQueue()
    if HAS_FAKEREDIS:
        yield "redis", RedisTaskQueue()


class TestTaskQueueContract(unittest.TestCase):

    def _run_for_all(self, test_fn):
        for name, q in _create_queues():
            with self.subTest(backend=name):
                try:
                    test_fn(q)
                finally:
                    q.close()

    def test_enqueue_dequeue(self):
        def _test(q):
            item = TaskItem(task_id="t1", queue_name="work", payload={"x": 1})
            q.enqueue(item)
            self.assertEqual(q.queue_length("work"), 1)
            got = q.dequeue("work", worker_id="w1")
            self.assertIsNotNone(got)
            self.assertEqual(got.task_id, "t1")
            self.assertEqual(got.status, "processing")
            self.assertEqual(got.attempt_count, 1)
            self.assertEqual(q.queue_length("work"), 0)
        self._run_for_all(_test)

    def test_dequeue_empty(self):
        def _test(q):
            self.assertIsNone(q.dequeue("empty"))
        self._run_for_all(_test)

    def test_ack(self):
        def _test(q):
            q.enqueue(TaskItem(task_id="t2", queue_name="work", payload={}))
            q.dequeue("work")
            self.assertTrue(q.ack("t2"))
            self.assertFalse(q.ack("t2"))  # already acked
        self._run_for_all(_test)

    def test_nack_retries(self):
        def _test(q):
            item = TaskItem(task_id="t3", queue_name="work", payload={}, max_retries=2)
            q.enqueue(item)
            # First attempt -> nack -> back to queue
            q.dequeue("work")
            q.nack("t3", error="fail1")
            self.assertEqual(q.queue_length("work"), 1)
            # Second attempt -> nack -> dead letter (attempt_count=2 >= max_retries=2)
            q.dequeue("work")
            q.nack("t3", error="fail2")
            self.assertEqual(q.queue_length("work"), 0)
            dead = q.peek_dead_letter("work")
            self.assertEqual(len(dead), 1)
            self.assertEqual(dead[0].task_id, "t3")
            self.assertEqual(dead[0].status, "dead")
        self._run_for_all(_test)

    def test_fifo_order(self):
        def _test(q):
            q.enqueue(TaskItem(task_id="a", queue_name="q", payload={}))
            q.enqueue(TaskItem(task_id="b", queue_name="q", payload={}))
            q.enqueue(TaskItem(task_id="c", queue_name="q", payload={}))
            self.assertEqual(q.dequeue("q").task_id, "a")
            self.assertEqual(q.dequeue("q").task_id, "b")
            self.assertEqual(q.dequeue("q").task_id, "c")
        self._run_for_all(_test)


if __name__ == "__main__":
    unittest.main()
