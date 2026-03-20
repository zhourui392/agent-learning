"""Resilience scorer -- grade system behavior under chaos scenarios."""

from __future__ import annotations

from typing import Dict, List

from src.chaos.models import ChaosResult, ResilienceReport


_WEAKNESS_THRESHOLD = 0.7


class ResilienceScorer:
    """Score resilience from a set of chaos experiment results.

    Dimensions
    ----------
    - Recovery speed: fast recovery → higher score
    - Error isolation: errors contained to target component → higher score
    - Cascading failure: no cascade → higher score

    Each dimension is 0.0-1.0; the overall score is the mean.
    """

    def __init__(self, max_recovery_ms: float = 5000.0) -> None:
        self._max_recovery_ms = max_recovery_ms

    def score(self, results: List[ChaosResult]) -> ResilienceReport:
        """Produce a resilience report from chaos results."""
        if not results:
            return ResilienceReport(overall_score=1.0)

        scenario_scores: Dict[str, float] = {}
        weaknesses: List[str] = []

        for result in results:
            label = f"{result.scenario.fault_type}:{result.scenario.target_component}"
            s = self._score_single(result)
            scenario_scores[label] = round(s, 4)
            if s < _WEAKNESS_THRESHOLD:
                weaknesses.append(label)

        overall = sum(scenario_scores.values()) / len(scenario_scores)

        return ResilienceReport(
            overall_score=round(overall, 4),
            scenario_scores=scenario_scores,
            weaknesses=weaknesses,
            details=results,
        )

    def _score_single(self, result: ChaosResult) -> float:
        recovery_score = max(
            0.0,
            1.0 - result.recovery_time_ms / self._max_recovery_ms,
        )
        isolation_score = 1.0 if result.error_isolated else 0.0
        cascade_score = 0.0 if result.cascading_failure else 1.0

        return (recovery_score + isolation_score + cascade_score) / 3.0
