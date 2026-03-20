"""Tests for BusinessEvaluator."""

import unittest

from src.config_center.config_store import ConfigCenter
from src.evaluation.business_evaluator import InMemoryBusinessEvaluator
from src.evaluation.models import BusinessMetrics


class TestInMemoryBusinessEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = InMemoryBusinessEvaluator()

    def test_evaluate_high_quality_passes(self):
        summary = {"e2e_success_rate": 0.95, "stability": 1.0}
        biz = BusinessMetrics(revenue_impact=0.9, cost_efficiency=0.8, user_satisfaction=0.85)
        score = self.evaluator.evaluate(summary, biz, alert_firing_count=0)
        self.assertTrue(score.passed)
        self.assertGreater(score.overall_score, 0.7)

    def test_evaluate_low_quality_fails(self):
        summary = {"e2e_success_rate": 0.3, "stability": 0.5}
        biz = BusinessMetrics(revenue_impact=0.2, cost_efficiency=0.2, user_satisfaction=0.2)
        score = self.evaluator.evaluate(summary, biz, alert_firing_count=0)
        self.assertFalse(score.passed)

    def test_alerts_cause_failure(self):
        summary = {"e2e_success_rate": 0.95, "stability": 1.0}
        biz = BusinessMetrics(revenue_impact=0.9, cost_efficiency=0.9, user_satisfaction=0.9)
        score = self.evaluator.evaluate(summary, biz, alert_firing_count=2)
        self.assertFalse(score.passed)
        self.assertIn("alert", score.reasons[0].lower() if score.reasons else "")

    def test_composite_score_breakdown(self):
        summary = {"e2e_success_rate": 1.0, "stability": 1.0}
        biz = BusinessMetrics(revenue_impact=1.0, cost_efficiency=1.0, user_satisfaction=1.0)
        score = self.evaluator.evaluate(summary, biz)
        self.assertIn("e2e_success_rate", score.breakdown)
        self.assertIn("revenue_impact", score.breakdown)

    def test_custom_weights(self):
        evaluator = InMemoryBusinessEvaluator(
            weights={"technical": 0.3, "business": 0.7},
            pass_threshold=0.5,
        )
        summary = {"e2e_success_rate": 0.5, "stability": 0.5}
        biz = BusinessMetrics(revenue_impact=0.9, cost_efficiency=0.9, user_satisfaction=0.9)
        score = evaluator.evaluate(summary, biz)
        self.assertTrue(score.passed)

    def test_from_config_center(self):
        cc = ConfigCenter()
        cc.put("business_eval", "weights", {"technical": 0.5, "business": 0.5})
        cc.put("business_eval", "pass_threshold", 0.6)
        evaluator = InMemoryBusinessEvaluator.from_config_center(cc)
        summary = {"e2e_success_rate": 0.8, "stability": 1.0}
        biz = BusinessMetrics(revenue_impact=0.8, cost_efficiency=0.8, user_satisfaction=0.8)
        score = evaluator.evaluate(summary, biz)
        self.assertTrue(score.passed)

    def test_from_config_center_empty_fallback(self):
        cc = ConfigCenter()
        evaluator = InMemoryBusinessEvaluator.from_config_center(cc)
        self.assertIsNotNone(evaluator)


if __name__ == "__main__":
    unittest.main()
