"""Tests for ReplayScheduler."""

import unittest

from src.config_center.config_store import ConfigCenter
from src.replay.replay_scheduler import ReplayScheduler
from src.scheduler.in_memory_queue import InMemoryTaskQueue


class TestReplayScheduler(unittest.TestCase):
    def setUp(self):
        self.queue = InMemoryTaskQueue()
        self.cc = ConfigCenter()
        self.scheduler = ReplayScheduler(
            task_queue=self.queue,
            config_center=self.cc,
        )

    def test_schedule_enqueues_task(self):
        task_id = self.scheduler.schedule("data/failed-cases.jsonl", run_id="r1")
        self.assertEqual(task_id, "r1")
        self.assertEqual(self.scheduler.pending_count(), 1)

    def test_schedule_auto_id(self):
        task_id = self.scheduler.schedule("data/test.jsonl")
        self.assertTrue(len(task_id) > 0)

    def test_current_policy_default(self):
        policy = self.scheduler.current_policy()
        self.assertEqual(policy.throttle_rate, 1.0)
        self.assertEqual(policy.sample_ratio, 1.0)

    def test_current_policy_from_config(self):
        self.cc.put("replay_policy", "default", {
            "throttle_rate": 0.5,
            "sample_ratio": 0.3,
            "target_variant": "variant_a",
            "max_batch_size": 20,
        })
        policy = self.scheduler.current_policy()
        self.assertEqual(policy.throttle_rate, 0.5)
        self.assertEqual(policy.sample_ratio, 0.3)
        self.assertEqual(policy.target_variant, "variant_a")
        self.assertEqual(policy.max_batch_size, 20)


if __name__ == "__main__":
    unittest.main()
