"""W11 integration test: full regression pipeline end-to-end with InMemory backends."""

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
from src.ops_report.weekly_report_generator import WeeklyReportGenerator
from src.replay.replay_engine import InMemoryReplayEngine
from src.replay.models import ReplayRecord


class TestW11RegressionPipelineIntegration(unittest.TestCase):
    """End-to-end test of the full W11 regression pipeline."""

    def setUp(self):
        self.cc = ConfigCenter()
        self.bus = InMemoryMessageBus()
        self.replay_engine = InMemoryReplayEngine()

        # Pre-load some replay records
        for i in range(5):
            self.replay_engine.capture(ReplayRecord(
                case_id=f"case-{i}",
                anonymized=True,
                sample={"query": f"test query {i}"},
            ))

        self.pipeline = RegressionPipeline(
            replay_engine=self.replay_engine,
            chaos_injector=InMemoryChaosInjector(),
            business_evaluator=InMemoryBusinessEvaluator(),
            error_budget_tracker=ErrorBudgetTracker(slo_target=0.99),
            gate_function=GateFunction(),
            alert_manager=AlertManager(),
            message_bus=self.bus,
            config_center=self.cc,
            evaluate_fn=lambda path: {
                "e2e_success_rate": 0.92,
                "stability": 1.0,
                "total_samples": 50,
                "avg_answer_f1": 0.75,
                "cost": {"total_tokens": 300},
            },
        )

    def test_full_pipeline_with_chaos(self):
        config = RegressionRunConfig(
            run_id="integ-run-1",
            dataset_path="eval/datasets/smoke.jsonl",
            chaos_scenarios=[
                ChaosScenario(fault_type="latency", target_component="rag",
                              parameters={"delay_ms": 1}),
                ChaosScenario(fault_type="latency", target_component="gateway",
                              parameters={"delay_ms": 1}),
            ],
        )
        result = self.pipeline.run(config)

        # All steps completed
        self.assertIn("replay", result.steps_completed)
        self.assertIn("evaluate", result.steps_completed)
        self.assertIn("chaos", result.steps_completed)
        self.assertIn("gate", result.steps_completed)

        # Resilience report generated
        self.assertIsNotNone(result.resilience_report)
        self.assertGreater(result.resilience_report.overall_score, 0.0)

        # Result stored in ConfigCenter
        entry = self.cc.get("regression_results", "integ-run-1")
        self.assertIsNotNone(entry)

    def test_pipeline_results_feed_weekly_report(self):
        """Run pipeline multiple times, then generate a weekly report."""
        for i in range(3):
            config = RegressionRunConfig(
                run_id=f"report-run-{i}",
                dataset_path="eval/datasets/smoke.jsonl",
                enable_chaos=False,
            )
            self.pipeline.run(config)

        generator = WeeklyReportGenerator(self.cc)
        md = generator.render_markdown("2026-03-10", "2026-03-17")
        self.assertIn("Weekly Ops Report", md)
        self.assertIn("report-run-0", md)
        self.assertEqual(generator.generate("2026-03-10", "2026-03-17").total_runs, 3)

    def test_message_bus_events_sequence(self):
        events = []
        for topic in [
            "regression.started", "regression.completed",
            "regression.step.replay", "regression.step.evaluate",
            "regression.step.gate",
        ]:
            self.bus.subscribe(topic, lambda m, t=topic: events.append(t))

        config = RegressionRunConfig(
            run_id="event-integ",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )
        self.pipeline.run(config)

        self.assertIn("regression.started", events)
        self.assertIn("regression.completed", events)
        self.assertIn("regression.step.evaluate", events)
        self.assertIn("regression.step.gate", events)


if __name__ == "__main__":
    unittest.main()
