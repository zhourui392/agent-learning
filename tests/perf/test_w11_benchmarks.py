"""W11 performance benchmarks: replay throughput, anonymizer throughput, pipeline latency."""

import time
import unittest

from src.automation.gate_function import GateFunction
from src.automation.models import RegressionRunConfig
from src.automation.regression_pipeline import RegressionPipeline
from src.chaos.chaos_injector import InMemoryChaosInjector
from src.config_center.config_store import ConfigCenter
from src.evaluation.business_evaluator import InMemoryBusinessEvaluator
from src.evaluation.error_budget_tracker import ErrorBudgetTracker
from src.messaging.in_memory_bus import InMemoryMessageBus
from src.observability.alert_manager import AlertManager
from src.replay.anonymizer import TrafficAnonymizer
from src.replay.models import ReplayPolicy, ReplayRecord, ReplayResult
from src.replay.replay_engine import InMemoryReplayEngine


class TestW11Benchmarks(unittest.TestCase):
    """Performance benchmarks for W11 components."""

    def test_anonymizer_throughput(self):
        """Anonymize 1000 records in under 1 second."""
        anon = TrafficAnonymizer()
        record = {
            "case_id": "c1",
            "sample": {
                "query": "Call 13812345678 or email user@example.com, ID 110101199001011234",
                "expected_answer": "Some answer with phone 13912345678",
            },
        }

        start = time.monotonic()
        for _ in range(1000):
            anon.anonymize_record(record)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 1.0, f"Anonymizer took {elapsed:.3f}s for 1000 records")

    def test_replay_throughput(self):
        """Replay 500 records in under 2 seconds."""
        engine = InMemoryReplayEngine()
        for i in range(500):
            engine.capture(ReplayRecord(case_id=f"c{i}", anonymized=True))

        def fast_executor(rec):
            return ReplayResult(record_id=rec.case_id, success=True, latency_ms=0.1)

        start = time.monotonic()
        batch = engine.replay(ReplayPolicy(max_batch_size=500), fast_executor)
        elapsed = time.monotonic() - start

        self.assertEqual(len(batch.results), 500)
        self.assertLess(elapsed, 2.0, f"Replay took {elapsed:.3f}s for 500 records")

    def test_pipeline_latency(self):
        """Full pipeline completes in under 2 seconds."""
        pipeline = RegressionPipeline(
            replay_engine=InMemoryReplayEngine(),
            chaos_injector=InMemoryChaosInjector(),
            business_evaluator=InMemoryBusinessEvaluator(),
            error_budget_tracker=ErrorBudgetTracker(),
            gate_function=GateFunction(),
            alert_manager=AlertManager(),
            message_bus=InMemoryMessageBus(),
            config_center=ConfigCenter(),
            evaluate_fn=lambda path: {
                "e2e_success_rate": 0.9,
                "stability": 1.0,
                "total_samples": 50,
                "avg_answer_f1": 0.8,
                "cost": {"total_tokens": 200},
            },
        )

        config = RegressionRunConfig(
            run_id="perf-run",
            dataset_path="test.jsonl",
            enable_chaos=False,
        )

        start = time.monotonic()
        result = pipeline.run(config)
        elapsed = time.monotonic() - start

        self.assertIsNotNone(result.gate_decision)
        self.assertLess(elapsed, 2.0, f"Pipeline took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
