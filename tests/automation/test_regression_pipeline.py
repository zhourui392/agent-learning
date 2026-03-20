"""Tests for RegressionPipeline."""

import unittest

from src.automation.gate_function import GateFunction
from src.automation.models import RegressionRunConfig
from src.automation.regression_pipeline import RegressionPipeline
from src.chaos.chaos_injector import InMemoryChaosInjector
from src.chaos.models import ChaosScenario
from src.config_center.config_store import ConfigCenter
from src.evaluation.business_evaluator import InMemoryBusinessEvaluator
from src.evaluation.error_budget_tracker import ErrorBudgetTracker
from src.messaging.in_memory_bus import InMemoryMessageBus
from src.observability.alert_manager import AlertManager
from src.replay.replay_engine import InMemoryReplayEngine


class TestRegressionPipeline(unittest.TestCase):
    def setUp(self):
        self.cc = ConfigCenter()
        self.bus = InMemoryMessageBus()
        self.pipeline = RegressionPipeline(
            replay_engine=InMemoryReplayEngine(),
            chaos_injector=InMemoryChaosInjector(),
            business_evaluator=InMemoryBusinessEvaluator(),
            error_budget_tracker=ErrorBudgetTracker(),
            gate_function=GateFunction(),
            alert_manager=AlertManager(),
            message_bus=self.bus,
            config_center=self.cc,
            evaluate_fn=lambda path: {
                "e2e_success_rate": 0.95,
                "stability": 1.0,
                "total_samples": 100,
                "avg_answer_f1": 0.8,
                "cost": {"total_tokens": 500},
            },
        )

    def test_run_full_pipeline(self):
        config = RegressionRunConfig(
            run_id="test-run-1",
            dataset_path="eval/datasets/smoke.jsonl",
            enable_replay=True,
            enable_chaos=True,
            chaos_scenarios=[
                ChaosScenario(fault_type="latency", target_component="rag",
                              parameters={"delay_ms": 1}),
            ],
        )
        result = self.pipeline.run(config)
        self.assertEqual(result.run_id, "test-run-1")
        self.assertIn("replay", result.steps_completed)
        self.assertIn("evaluate", result.steps_completed)
        self.assertIn("chaos", result.steps_completed)
        self.assertIn("gate", result.steps_completed)

    def test_gate_decision_present(self):
        config = RegressionRunConfig(
            run_id="test-run-2",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )
        result = self.pipeline.run(config)
        self.assertIsNotNone(result.gate_decision)

    def test_results_stored_in_config_center(self):
        config = RegressionRunConfig(
            run_id="stored-run",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )
        self.pipeline.run(config)
        entry = self.cc.get("regression_results", "stored-run")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.value["run_id"], "stored-run")

    def test_events_published_to_bus(self):
        received = []
        self.bus.subscribe("regression.started", lambda m: received.append(m.topic))
        self.bus.subscribe("regression.completed", lambda m: received.append(m.topic))

        config = RegressionRunConfig(
            run_id="event-run",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )
        self.pipeline.run(config)
        self.assertIn("regression.started", received)
        self.assertIn("regression.completed", received)

    def test_no_chaos_skips_step(self):
        config = RegressionRunConfig(
            run_id="no-chaos",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )
        result = self.pipeline.run(config)
        self.assertNotIn("chaos", result.steps_completed)


if __name__ == "__main__":
    unittest.main()
