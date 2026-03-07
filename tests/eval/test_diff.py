"""Unit tests for W5 baseline diff."""

from __future__ import annotations

import unittest

from eval.diff import DiffThresholds, compare_reports


class EvalDiffTestCase(unittest.TestCase):
    """Verify baseline diff gating logic."""

    def test_compare_reports_passes_without_regression(self) -> None:
        """Healthy current report should pass diff gate."""

        baseline = {
            "e2e_success_rate": 0.8,
            "avg_answer_f1": 0.6,
            "accuracy": 0.7,
            "p95_latency_ms": 100.0,
            "cost": {"total_tokens": 1000},
        }
        current = {
            "e2e_success_rate": 0.82,
            "avg_answer_f1": 0.61,
            "accuracy": 0.72,
            "p95_latency_ms": 110.0,
            "cost": {"total_tokens": 1100},
        }

        result = compare_reports(baseline, current, DiffThresholds())

        self.assertTrue(result.passed)
        self.assertEqual(result.issues, [])

    def test_compare_reports_fails_on_quality_regression(self) -> None:
        """Large regression should produce blocking issues."""

        baseline = {
            "e2e_success_rate": 0.8,
            "avg_answer_f1": 0.6,
            "accuracy": 0.7,
            "p95_latency_ms": 100.0,
            "cost": {"total_tokens": 1000},
        }
        current = {
            "e2e_success_rate": 0.6,
            "avg_answer_f1": 0.4,
            "accuracy": 0.5,
            "p95_latency_ms": 150.0,
            "cost": {"total_tokens": 1400},
        }

        result = compare_reports(baseline, current, DiffThresholds())

        self.assertFalse(result.passed)
        self.assertGreaterEqual(len(result.issues), 3)


if __name__ == "__main__":
    unittest.main()
