"""Tests for GateFunction."""

import unittest

from src.automation.gate_function import GateFunction
from src.config_center.config_store import ConfigCenter
from src.evaluation.models import CompositeScore, ErrorBudgetSnapshot
from src.observability.alert_manager import AlertEvent


class TestGateFunction(unittest.TestCase):
    def setUp(self):
        self.gate = GateFunction()

    def test_pass_no_issues(self):
        alerts = [
            AlertEvent(name="r1", severity="P2", status="ok",
                       metric="m", actual_value=0.0, threshold=1.0,
                       route="", description=""),
        ]
        decision = self.gate.decide(alerts)
        self.assertTrue(decision.passed)

    def test_fail_p1_alert(self):
        alerts = [
            AlertEvent(name="critical", severity="P1", status="firing",
                       metric="m", actual_value=0.5, threshold=0.9,
                       route="oncall", description="bad"),
        ]
        decision = self.gate.decide(alerts)
        self.assertFalse(decision.passed)
        self.assertEqual(decision.blocking_alerts, 1)

    def test_fail_low_score(self):
        alerts = []
        score = CompositeScore(
            technical_score=0.5, business_score=0.3,
            overall_score=0.4, passed=False,
        )
        decision = self.gate.decide(alerts, composite_score=score)
        self.assertFalse(decision.passed)
        self.assertFalse(decision.score_ok)

    def test_fail_budget_exhausted(self):
        alerts = []
        budget = ErrorBudgetSnapshot(
            slo_target=0.99, total_observations=100,
            bad_observations=5, burn_rate=5.0, remaining=0.0,
        )
        decision = self.gate.decide(alerts, budget_snapshot=budget)
        self.assertFalse(decision.passed)
        self.assertFalse(decision.budget_ok)

    def test_from_config_center(self):
        cc = ConfigCenter()
        cc.put("gate_policy", "score_threshold", 0.8)
        cc.put("gate_policy", "max_p1_alerts", 1)
        gate = GateFunction.from_config_center(cc)
        alerts = [
            AlertEvent(name="a", severity="P1", status="firing",
                       metric="m", actual_value=0.5, threshold=0.9,
                       route="", description=""),
        ]
        decision = gate.decide(alerts)
        self.assertTrue(decision.passed)  # 1 P1 <= max_p1_alerts=1

    def test_multiple_reasons(self):
        alerts = [
            AlertEvent(name="a", severity="P1", status="firing",
                       metric="m", actual_value=0.5, threshold=0.9,
                       route="", description=""),
        ]
        score = CompositeScore(
            technical_score=0.3, business_score=0.2,
            overall_score=0.25, passed=False,
        )
        budget = ErrorBudgetSnapshot(
            slo_target=0.99, total_observations=100,
            bad_observations=10, burn_rate=10.0, remaining=0.0,
        )
        decision = self.gate.decide(alerts, score, budget)
        self.assertFalse(decision.passed)
        self.assertGreaterEqual(len(decision.reasons), 3)


if __name__ == "__main__":
    unittest.main()
