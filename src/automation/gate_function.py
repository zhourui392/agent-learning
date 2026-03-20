"""Gate function -- automated release decision based on alerts, score, and budget.

Gate policy is loaded from ConfigCenter namespace ``"gate_policy"``.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from src.automation.models import GateDecision

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter
    from src.evaluation.models import CompositeScore, ErrorBudgetSnapshot
    from src.observability.alert_manager import AlertEvent


_DEFAULT_SCORE_THRESHOLD = 0.7
_DEFAULT_MAX_P1_ALERTS = 0


class GateFunction:
    """Automated gate that blocks or approves a release.

    Decision rules (evaluated in order):
    1. Any P1 alert firing → fail
    2. Composite score below threshold → fail
    3. Error budget exhausted → fail
    """

    def __init__(
        self,
        score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
        max_p1_alerts: int = _DEFAULT_MAX_P1_ALERTS,
    ) -> None:
        self._score_threshold = score_threshold
        self._max_p1_alerts = max_p1_alerts

    @classmethod
    def from_config_center(
        cls,
        config_center: "ConfigCenter",
        namespace: str = "gate_policy",
    ) -> "GateFunction":
        """Load gate thresholds from ConfigCenter."""
        score_threshold = _DEFAULT_SCORE_THRESHOLD
        max_p1 = _DEFAULT_MAX_P1_ALERTS

        entry = config_center.get(namespace, "score_threshold")
        if entry is not None:
            score_threshold = float(entry.value)

        entry = config_center.get(namespace, "max_p1_alerts")
        if entry is not None:
            max_p1 = int(entry.value)

        return cls(score_threshold=score_threshold, max_p1_alerts=max_p1)

    def decide(
        self,
        alerts: List["AlertEvent"],
        composite_score: Optional["CompositeScore"] = None,
        budget_snapshot: Optional["ErrorBudgetSnapshot"] = None,
    ) -> GateDecision:
        """Evaluate the gate and return a decision."""
        reasons: List[str] = []

        p1_firing = sum(
            1 for a in alerts
            if a.severity == "P1" and a.status == "firing"
        )
        blocking_alerts = p1_firing

        if p1_firing > self._max_p1_alerts:
            reasons.append(f"{p1_firing} P1 alert(s) firing")

        score_ok = True
        if composite_score is not None:
            if composite_score.overall_score < self._score_threshold:
                score_ok = False
                reasons.append(
                    f"score {composite_score.overall_score:.3f} "
                    f"< threshold {self._score_threshold}"
                )

        budget_ok = True
        if budget_snapshot is not None:
            if budget_snapshot.remaining <= 0.0:
                budget_ok = False
                reasons.append("error budget exhausted")

        passed = len(reasons) == 0

        return GateDecision(
            passed=passed,
            reasons=reasons,
            blocking_alerts=blocking_alerts,
            budget_ok=budget_ok,
            score_ok=score_ok,
        )
