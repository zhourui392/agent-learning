"""Unit tests for W8 A/B routing helpers."""

from __future__ import annotations

import unittest

from src.release.ab_router import AbRouter, ExperimentConfig, MetricGuardrail, VariantAllocation


class AbRouterTestCase(unittest.TestCase):
    """Verify deterministic routing and safety guardrails."""

    def setUp(self) -> None:
        self.router = AbRouter()
        self.config = ExperimentConfig(
            experiment_id="refund-decision-exp",
            default_variant="control",
            salt="w8",
            variants=[
                VariantAllocation(name="control", percentage=90.0),
                VariantAllocation(name="assistant_v2", percentage=10.0),
            ],
            guardrails=[
                MetricGuardrail(metric="success_rate", comparator="lt", threshold=0.92),
                MetricGuardrail(metric="latency.p95_ms", comparator="gt", threshold=2500.0),
            ],
        )

    def test_route_is_deterministic_for_same_subject(self) -> None:
        """The same subject should always map to the same variant."""

        first_decision = self.router.route(self.config, "user-1001")
        second_decision = self.router.route(self.config, "user-1001")

        self.assertEqual(first_decision.variant, second_decision.variant)
        self.assertEqual(first_decision.bucket, second_decision.bucket)
        self.assertEqual("bucket_assignment", first_decision.reason)

    def test_disabled_experiment_returns_default_variant(self) -> None:
        """Disabled experiments should stop routing to treatment."""

        disabled_config = ExperimentConfig(
            experiment_id=self.config.experiment_id,
            default_variant=self.config.default_variant,
            variants=self.config.variants,
            enabled=False,
        )

        decision = self.router.route(disabled_config, "user-1002")

        self.assertEqual("control", decision.variant)
        self.assertEqual("experiment_disabled", decision.reason)

    def test_override_routes_to_requested_variant(self) -> None:
        """Manual override should support targeted verification."""

        decision = self.router.route(self.config, "qa-user", override_variant="assistant_v2")

        self.assertEqual("assistant_v2", decision.variant)
        self.assertEqual("manual_override", decision.reason)

    def test_invalid_percentage_sum_raises_error(self) -> None:
        """Invalid traffic allocation should be rejected early."""

        invalid_config = ExperimentConfig(
            experiment_id="bad-exp",
            default_variant="control",
            variants=[
                VariantAllocation(name="control", percentage=80.0),
                VariantAllocation(name="treatment", percentage=10.0),
            ],
        )

        with self.assertRaises(ValueError):
            self.router.route(invalid_config, "user-1003")

    def test_guardrails_can_stop_experiment(self) -> None:
        """Guardrail violations should request an immediate stop."""

        decision = self.router.evaluate_guardrails(
            self.config,
            {
                "success_rate": 0.90,
                "latency": {"p95_ms": 2800.0},
            },
        )

        self.assertTrue(decision.should_stop)
        self.assertEqual("stop", decision.status)
        self.assertEqual(2, len(decision.hits))

    def test_guardrails_stay_ok_when_metrics_are_healthy(self) -> None:
        """Healthy metrics should keep the experiment running."""

        decision = self.router.evaluate_guardrails(
            self.config,
            {
                "success_rate": 0.97,
                "latency": {"p95_ms": 1800.0},
            },
        )

        self.assertFalse(decision.should_stop)
        self.assertEqual("ok", decision.status)
        self.assertEqual([], decision.hits)


if __name__ == "__main__":
    unittest.main()
