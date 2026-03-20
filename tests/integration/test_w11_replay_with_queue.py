"""W11 integration test: ReplayScheduler + TaskQueue."""

import unittest

from src.config_center.config_store import ConfigCenter
from src.replay.replay_scheduler import ReplayScheduler
from src.scheduler.in_memory_queue import InMemoryTaskQueue


class TestW11ReplayWithQueue(unittest.TestCase):
    """Integration test for ReplayScheduler scheduling through TaskQueue."""

    def setUp(self):
        self.queue = InMemoryTaskQueue()
        self.cc = ConfigCenter()
        self.scheduler = ReplayScheduler(
            task_queue=self.queue,
            config_center=self.cc,
        )

    def test_schedule_and_dequeue(self):
        task_id = self.scheduler.schedule("eval/datasets/smoke.jsonl", run_id="q-run-1")
        self.assertEqual(self.scheduler.pending_count(), 1)

        item = self.queue.dequeue("replay_tasks", worker_id="w1")
        self.assertIsNotNone(item)
        self.assertEqual(item.task_id, "q-run-1")
        self.assertEqual(item.payload["action"], "replay")

    def test_policy_passed_in_payload(self):
        self.cc.put("replay_policy", "default", {
            "throttle_rate": 0.5,
            "sample_ratio": 0.2,
            "target_variant": "variant_b",
            "max_batch_size": 10,
        })
        self.scheduler.schedule("data.jsonl", run_id="q-run-2")
        item = self.queue.dequeue("replay_tasks", worker_id="w1")
        policy = item.payload["policy"]
        self.assertEqual(policy["throttle_rate"], 0.5)
        self.assertEqual(policy["sample_ratio"], 0.2)
        self.assertEqual(policy["target_variant"], "variant_b")

    def test_multiple_schedules(self):
        for i in range(5):
            self.scheduler.schedule("data.jsonl", run_id=f"batch-{i}")
        self.assertEqual(self.scheduler.pending_count(), 5)

    def test_ack_completes_task(self):
        self.scheduler.schedule("data.jsonl", run_id="ack-test")
        item = self.queue.dequeue("replay_tasks", worker_id="w1")
        self.assertTrue(self.queue.ack(item.task_id))
        self.assertEqual(self.scheduler.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
