"""Business metrics evaluator -- combines technical and business signals.

W11 module: weights are loaded from ConfigCenter namespace ``"business_eval"``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.evaluation.models import BusinessMetrics, CompositeScore

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


_DEFAULT_WEIGHTS: Dict[str, float] = {
    "technical": 0.6,
    "business": 0.4,
}

_DEFAULT_BUSINESS_WEIGHTS: Dict[str, float] = {
    "revenue_impact": 0.4,
    "cost_efficiency": 0.3,
    "user_satisfaction": 0.3,
}

_DEFAULT_PASS_THRESHOLD: float = 0.7


class BusinessEvaluator(ABC):
    """Abstract business evaluator."""

    @abstractmethod
    def evaluate(
        self,
        technical_summary: Dict[str, Any],
        business_metrics: BusinessMetrics,
        alert_firing_count: int = 0,
    ) -> CompositeScore:
        """Produce a composite score from technical + business signals."""


class InMemoryBusinessEvaluator(BusinessEvaluator):
    """In-memory implementation with configurable weights.

    Parameters
    ----------
    weights : dict, optional
        Top-level ``{"technical": float, "business": float}``.
    business_weights : dict, optional
        Sub-weights for business dimensions.
    pass_threshold : float
        Minimum overall score to pass.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        business_weights: Optional[Dict[str, float]] = None,
        pass_threshold: float = _DEFAULT_PASS_THRESHOLD,
    ) -> None:
        self._weights = weights or dict(_DEFAULT_WEIGHTS)
        self._business_weights = business_weights or dict(_DEFAULT_BUSINESS_WEIGHTS)
        self._pass_threshold = pass_threshold

    @classmethod
    def from_config_center(
        cls,
        config_center: "ConfigCenter",
        namespace: str = "business_eval",
    ) -> "InMemoryBusinessEvaluator":
        """Load evaluator weights from ConfigCenter."""
        weights: Dict[str, float] = dict(_DEFAULT_WEIGHTS)
        business_weights: Dict[str, float] = dict(_DEFAULT_BUSINESS_WEIGHTS)
        pass_threshold = _DEFAULT_PASS_THRESHOLD

        entry = config_center.get(namespace, "weights")
        if entry is not None and isinstance(entry.value, dict):
            weights.update(entry.value)

        entry = config_center.get(namespace, "business_weights")
        if entry is not None and isinstance(entry.value, dict):
            business_weights.update(entry.value)

        entry = config_center.get(namespace, "pass_threshold")
        if entry is not None:
            pass_threshold = float(entry.value)

        return cls(
            weights=weights,
            business_weights=business_weights,
            pass_threshold=pass_threshold,
        )

    def evaluate(
        self,
        technical_summary: Dict[str, Any],
        business_metrics: BusinessMetrics,
        alert_firing_count: int = 0,
    ) -> CompositeScore:
        technical_score = self._compute_technical_score(
            technical_summary, alert_firing_count,
        )
        business_score = self._compute_business_score(business_metrics)

        w_tech = self._weights.get("technical", 0.6)
        w_biz = self._weights.get("business", 0.4)
        overall = w_tech * technical_score + w_biz * business_score

        reasons: List[str] = []
        if overall < self._pass_threshold:
            reasons.append(
                f"overall {overall:.3f} < threshold {self._pass_threshold}"
            )
        if alert_firing_count > 0:
            reasons.append(f"{alert_firing_count} alert(s) firing")

        return CompositeScore(
            technical_score=round(technical_score, 4),
            business_score=round(business_score, 4),
            overall_score=round(overall, 4),
            passed=overall >= self._pass_threshold and alert_firing_count == 0,
            breakdown={
                "e2e_success_rate": float(
                    technical_summary.get("e2e_success_rate", 0.0)
                ),
                "revenue_impact": business_metrics.revenue_impact,
                "cost_efficiency": business_metrics.cost_efficiency,
                "user_satisfaction": business_metrics.user_satisfaction,
            },
            reasons=reasons,
        )

    def _compute_technical_score(
        self,
        summary: Dict[str, Any],
        alert_firing_count: int,
    ) -> float:
        e2e = float(summary.get("e2e_success_rate", 0.0))
        stability = float(summary.get("stability", 1.0))
        alert_penalty = min(alert_firing_count * 0.1, 0.5)
        return max(0.0, (e2e * 0.7 + stability * 0.3) - alert_penalty)

    def _compute_business_score(self, metrics: BusinessMetrics) -> float:
        bw = self._business_weights
        return (
            bw.get("revenue_impact", 0.4) * metrics.revenue_impact
            + bw.get("cost_efficiency", 0.3) * metrics.cost_efficiency
            + bw.get("user_satisfaction", 0.3) * metrics.user_satisfaction
        )
