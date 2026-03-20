"""Tests for ResilienceScorer."""

import unittest

from src.chaos.models import ChaosResult, ChaosScenario
from src.chaos.resilience_scorer import ResilienceScorer


class TestResilienceScorer(unittest.TestCase):
    def test_empty_results(self):
        scorer = ResilienceScorer()
        report = scorer.score([])
        self.assertEqual(report.overall_score, 1.0)

    def test_perfect_resilience(self):
        scorer = ResilienceScorer(max_recovery_ms=1000.0)
        results = [
            ChaosResult(
                scenario=ChaosScenario(fault_type="latency", target_component="rag"),
                success=True,
                recovery_time_ms=10.0,
                error_isolated=True,
                cascading_failure=False,
            ),
        ]
        report = scorer.score(results)
        self.assertGreater(report.overall_score, 0.9)
        self.assertEqual(len(report.weaknesses), 0)

    def test_poor_resilience_detected(self):
        scorer = ResilienceScorer(max_recovery_ms=100.0)
        results = [
            ChaosResult(
                scenario=ChaosScenario(fault_type="error", target_component="api"),
                success=False,
                recovery_time_ms=200.0,
                error_isolated=False,
                cascading_failure=True,
            ),
        ]
        report = scorer.score(results)
        self.assertLess(report.overall_score, 0.7)
        self.assertGreater(len(report.weaknesses), 0)

    def test_mixed_results(self):
        scorer = ResilienceScorer(max_recovery_ms=1000.0)
        results = [
            ChaosResult(
                scenario=ChaosScenario(fault_type="latency", target_component="a"),
                success=True, recovery_time_ms=50.0,
                error_isolated=True, cascading_failure=False,
            ),
            ChaosResult(
                scenario=ChaosScenario(fault_type="error", target_component="b"),
                success=False, recovery_time_ms=900.0,
                error_isolated=False, cascading_failure=True,
            ),
        ]
        report = scorer.score(results)
        self.assertEqual(len(report.scenario_scores), 2)


if __name__ == "__main__":
    unittest.main()
