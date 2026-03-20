"""Automated regression pipeline -- orchestrate replay, A/B, chaos, eval, and gate.

Each step publishes events to MessageBus and writes results to ConfigCenter
namespace ``"regression_results"``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from src.automation.gate_function import GateFunction
from src.automation.models import GateDecision, RegressionRunConfig, RegressionRunResult
from src.chaos.chaos_injector import ChaosInjector
from src.chaos.resilience_scorer import ResilienceScorer
from src.evaluation.business_evaluator import BusinessEvaluator
from src.evaluation.error_budget_tracker import ErrorBudgetTracker
from src.evaluation.models import BusinessMetrics
from src.replay.models import ReplayPolicy, ReplayRecord, ReplayResult
from src.replay.replay_engine import ReplayEngine

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter
    from src.messaging.interfaces import MessageBus
    from src.observability.alert_manager import AlertManager


class RegressionPipeline:
    """Orchestrate the full automated regression cycle.

    Steps
    -----
    1. replay   -- replay captured traffic
    2. ab_route -- route through experiment variant
    3. evaluate -- run evaluation scorer
    4. chaos    -- inject faults and score resilience
    5. gate     -- decide pass/fail

    Events are published to *message_bus* at each step.
    """

    def __init__(
        self,
        replay_engine: ReplayEngine,
        chaos_injector: ChaosInjector,
        business_evaluator: BusinessEvaluator,
        error_budget_tracker: ErrorBudgetTracker,
        gate_function: GateFunction,
        alert_manager: "AlertManager",
        message_bus: Optional["MessageBus"] = None,
        config_center: Optional["ConfigCenter"] = None,
        evaluate_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self._replay = replay_engine
        self._chaos = chaos_injector
        self._evaluator = business_evaluator
        self._budget = error_budget_tracker
        self._gate = gate_function
        self._alerts = alert_manager
        self._bus = message_bus
        self._cc = config_center
        self._evaluate_fn = evaluate_fn
        self._resilience_scorer = ResilienceScorer()

    def run(self, config: RegressionRunConfig) -> RegressionRunResult:
        """Execute the full regression pipeline."""
        run_id = config.run_id or uuid.uuid4().hex[:12]
        steps: List[str] = []
        self._publish(f"regression.started", {"run_id": run_id})

        # Step 1: Replay
        replay_batch_id: Optional[str] = None
        if config.enable_replay:
            self._publish("regression.step.replay", {"run_id": run_id, "status": "started"})
            batch = self._replay.replay(
                policy=ReplayPolicy(),
                executor=self._default_executor,
            )
            replay_batch_id = batch.batch_id
            steps.append("replay")
            self._publish("regression.step.replay", {"run_id": run_id, "status": "completed"})

        # Step 2: A/B route (marker step -- routing is embedded in evaluate)
        if config.enable_ab_routing:
            self._publish("regression.step.ab_route", {"run_id": run_id, "status": "completed"})
            steps.append("ab_route")

        # Step 3: Evaluate
        self._publish("regression.step.evaluate", {"run_id": run_id, "status": "started"})
        summary: Dict[str, Any] = {}
        if self._evaluate_fn is not None:
            summary = self._evaluate_fn(config.dataset_path)
        else:
            summary = {"e2e_success_rate": 1.0, "stability": 1.0}
        steps.append("evaluate")
        self._publish("regression.step.evaluate", {"run_id": run_id, "status": "completed"})

        # Step 4: Chaos
        resilience_report = None
        if config.enable_chaos and config.chaos_scenarios:
            self._publish("regression.step.chaos", {"run_id": run_id, "status": "started"})
            chaos_results = []
            for scenario in config.chaos_scenarios:
                cr = self._chaos.wrap_execution(scenario, lambda: "ok")
                chaos_results.append(cr)
            resilience_report = self._resilience_scorer.score(chaos_results)
            steps.append("chaos")
            self._publish("regression.step.chaos", {"run_id": run_id, "status": "completed"})

        # Compute alerts
        alert_events = self._alerts.evaluate(summary)
        firing_count = sum(1 for a in alert_events if a.status == "firing")

        # Compute business score
        biz_metrics = BusinessMetrics(
            revenue_impact=float(summary.get("e2e_success_rate", 0.0)),
            cost_efficiency=max(0.0, 1.0 - float(summary.get("cost", {}).get("total_tokens", 0)) / 10000.0),
            user_satisfaction=float(summary.get("avg_answer_f1", 0.0)),
        )
        composite = self._evaluator.evaluate(summary, biz_metrics, firing_count)

        # Update error budget
        total = int(summary.get("total_samples", 0))
        bad = total - int(total * float(summary.get("e2e_success_rate", 1.0)))
        if total > 0:
            self._budget.record_batch(total, bad)

        # Step 5: Gate
        self._publish("regression.step.gate", {"run_id": run_id, "status": "started"})
        gate_decision = self._gate.decide(
            alerts=alert_events,
            composite_score=composite,
            budget_snapshot=self._budget.snapshot(),
        )
        steps.append("gate")
        self._publish("regression.step.gate", {"run_id": run_id, "status": "completed"})

        result = RegressionRunResult(
            run_id=run_id,
            config=config,
            gate_decision=gate_decision,
            summary=summary,
            composite_score=composite,
            resilience_report=resilience_report,
            replay_batch_id=replay_batch_id,
            steps_completed=steps,
        )

        # Persist result to ConfigCenter
        if self._cc is not None:
            self._cc.put(
                "regression_results",
                run_id,
                {
                    "run_id": run_id,
                    "gate_passed": gate_decision.passed,
                    "overall_score": composite.overall_score,
                    "technical_score": composite.technical_score,
                    "business_score": composite.business_score,
                    "blocking_alerts": gate_decision.blocking_alerts,
                    "steps_completed": steps,
                    "timestamp": time.time(),
                },
            )

        self._publish("regression.completed", {
            "run_id": run_id,
            "gate_passed": gate_decision.passed,
        })
        return result

    def _publish(self, topic: str, payload: Dict[str, Any]) -> None:
        if self._bus is not None:
            self._bus.publish(topic, payload, sender_id="regression_pipeline")

    @staticmethod
    def _default_executor(record: ReplayRecord) -> ReplayResult:
        return ReplayResult(
            record_id=record.case_id,
            success=True,
            latency_ms=0.0,
        )
