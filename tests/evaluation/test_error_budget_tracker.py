"""Tests for ErrorBudgetTracker."""

import unittest

from src.config_center.config_store import ConfigCenter
from src.evaluation.error_budget_tracker import ErrorBudgetTracker


class TestErrorBudgetTracker(unittest.TestCase):
    def test_initial_snapshot(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        snap = tracker.snapshot()
        self.assertEqual(snap.total_observations, 0)
        self.assertEqual(snap.remaining, 1.0)

    def test_record_success(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        for _ in range(100):
            tracker.record(True)
        snap = tracker.snapshot()
        self.assertEqual(snap.total_observations, 100)
        self.assertEqual(snap.bad_observations, 0)
        self.assertEqual(snap.remaining, 1.0)

    def test_budget_exhausted(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        # 100 observations, 1% budget = 1 bad allowed
        for _ in range(98):
            tracker.record(True)
        tracker.record(False)
        tracker.record(False)
        self.assertTrue(tracker.is_budget_exhausted())

    def test_budget_not_exhausted(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        for _ in range(200):
            tracker.record(True)
        tracker.record(False)
        self.assertFalse(tracker.is_budget_exhausted())

    def test_record_batch(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        tracker.record_batch(1000, 5)
        snap = tracker.snapshot()
        self.assertEqual(snap.total_observations, 1000)
        self.assertEqual(snap.bad_observations, 5)
        self.assertFalse(tracker.is_budget_exhausted())

    def test_reset(self):
        tracker = ErrorBudgetTracker(slo_target=0.99)
        tracker.record_batch(100, 50)
        tracker.reset()
        snap = tracker.snapshot()
        self.assertEqual(snap.total_observations, 0)

    def test_invalid_slo(self):
        with self.assertRaises(ValueError):
            ErrorBudgetTracker(slo_target=0.0)
        with self.assertRaises(ValueError):
            ErrorBudgetTracker(slo_target=1.5)

    def test_from_config_center(self):
        cc = ConfigCenter()
        cc.put("slo_targets", "default", 0.995)
        tracker = ErrorBudgetTracker.from_config_center(cc)
        snap = tracker.snapshot()
        self.assertEqual(snap.slo_target, 0.995)

    def test_from_config_center_default(self):
        cc = ConfigCenter()
        tracker = ErrorBudgetTracker.from_config_center(cc)
        snap = tracker.snapshot()
        self.assertEqual(snap.slo_target, 0.995)


if __name__ == "__main__":
    unittest.main()
