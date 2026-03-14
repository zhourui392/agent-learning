"""End-to-end integration test for the full W10 distributed pipeline."""

from __future__ import annotations

import threading
import time
import unittest
from typing import List

from src.messaging.in_memory_bus import InMemoryMessageBus
from src.messaging.interfaces import Message
from src.observability.exporters.in_memory_metrics import InMemoryMetricsExporter
from src.observability.tracer import SpanRecord, TraceContext, Tracer
from src.observability.exporters.otlp_trace_exporter import OtlpJsonTraceExporter
from src.scheduler.in_memory_queue import InMemoryDistributedLock, InMemoryTaskQueue
from src.scheduler.interfaces import TaskItem


class TestEndToEndDistributedFlow(unittest.TestCase):
    """Bus → Queue → Worker → Metrics → Trace → Ack."""

    def test_full_pipeline(self):
        bus = InMemoryMessageBus()
        queue = InMemoryTaskQueue()
        metrics = InMemoryMetricsExporter()
        tracer = Tracer()
        completed: List[str] = []

        # Producer: listen for task requests on bus, enqueue to task queue
        def _on_task_request(msg: Message):
            queue.enqueue(TaskItem(
                task_id=msg.payload["task_id"],
                queue_name="pipeline",
                payload=msg.payload,
            ))
            metrics.counter("tasks_enqueued")

        bus.subscribe("task.request", _on_task_request)

        # Worker: dequeue and process
        def _worker():
            for _ in range(10):  # poll a few times
                item = queue.dequeue("pipeline", worker_id="worker-1")
                if item is None:
                    time.sleep(0.05)
                    continue
                # Simulate work with a trace span
                ctx = TraceContext(trace_id="tr1", session_id="s1", case_id="c1")
                with tracer.start_span(ctx, "worker", f"process_{item.task_id}"):
                    metrics.counter("tasks_processed")
                queue.ack(item.task_id)
                completed.append(item.task_id)

        # Publish 3 task requests via the bus
        for i in range(3):
            bus.publish("task.request", {"task_id": f"pipe_{i}"}, sender_id="producer")

        # Run worker in a thread
        worker_thread = threading.Thread(target=_worker)
        worker_thread.start()
        worker_thread.join(timeout=5.0)

        bus.close()

        # Verify
        self.assertEqual(len(completed), 3)
        snap = metrics.snapshot()
        self.assertEqual(snap["counters"]["tasks_enqueued"], 3.0)
        self.assertEqual(snap["counters"]["tasks_processed"], 3.0)
        self.assertEqual(len(tracer.list_spans()), 3)

    def test_multi_instance_simulation(self):
        """Simulate 3 instances sharing a queue via threading."""
        queue = InMemoryTaskQueue()
        lock = InMemoryDistributedLock()
        metrics = InMemoryMetricsExporter()

        for i in range(9):
            queue.enqueue(TaskItem(task_id=f"task_{i}", queue_name="shared", payload={}))

        processed: List[str] = []
        mu = threading.Lock()

        def _instance(instance_id: str):
            while True:
                item = queue.dequeue("shared", worker_id=instance_id)
                if item is None:
                    break
                if lock.acquire(f"task_{item.task_id}", holder_id=instance_id, timeout=0.1, ttl=2.0):
                    with mu:
                        processed.append(f"{instance_id}:{item.task_id}")
                    metrics.counter("processed", labels={"instance": instance_id})
                    lock.release(f"task_{item.task_id}", holder_id=instance_id)
                queue.ack(item.task_id)

        threads = [threading.Thread(target=_instance, args=(f"inst_{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(processed), 9)
        task_ids = [p.split(":")[1] for p in processed]
        self.assertEqual(len(set(task_ids)), 9)


if __name__ == "__main__":
    unittest.main()
