"""Trend analyzer -- detect regressions and improvements across runs.

Rules
-----
- 2 consecutive runs with >5 % decline on a metric → regression
- 2 consecutive runs with >10 % increase on a metric → improvement
- Slope of last 3 points determines overall_trend
"""

from __future__ import annotations

from typing import List

from src.ops_report.models import TrendAnalysis, TrendPoint


_REGRESSION_THRESHOLD = 0.05
_IMPROVEMENT_THRESHOLD = 0.10


class TrendAnalyzer:
    """Analyze metric trends across a series of TrendPoints."""

    def analyze(self, points: List[TrendPoint]) -> TrendAnalysis:
        if len(points) < 2:
            return TrendAnalysis()

        regressions: List[str] = []
        improvements: List[str] = []

        metric_keys = set()
        for p in points:
            metric_keys.update(p.metrics.keys())

        for key in sorted(metric_keys):
            values = [p.metrics.get(key) for p in points]
            # Check consecutive declines (regression)
            if self._consecutive_decline(values, _REGRESSION_THRESHOLD):
                regressions.append(key)
            # Check consecutive rises (improvement)
            if self._consecutive_rise(values, _IMPROVEMENT_THRESHOLD):
                improvements.append(key)

        overall_trend = self._compute_overall_trend(points)

        return TrendAnalysis(
            regressions=regressions,
            improvements=improvements,
            overall_trend=overall_trend,
        )

    def _consecutive_decline(
        self, values: List[float | None], threshold: float,
    ) -> bool:
        """Return True if last 2 consecutive diffs show decline > threshold."""
        nums = [v for v in values if v is not None]
        if len(nums) < 3:
            return False
        for i in range(len(nums) - 2, len(nums) - 1):
            prev, curr = nums[i - 1], nums[i]
            if prev == 0:
                continue
            if (prev - curr) / abs(prev) > threshold:
                next_prev, next_curr = nums[i], nums[i + 1] if i + 1 < len(nums) else nums[i]
                if next_prev == 0:
                    continue
                if i + 1 < len(nums) and (next_prev - next_curr) / abs(next_prev) > threshold:
                    return True
        return False

    def _consecutive_rise(
        self, values: List[float | None], threshold: float,
    ) -> bool:
        """Return True if last 2 consecutive diffs show rise > threshold."""
        nums = [v for v in values if v is not None]
        if len(nums) < 3:
            return False
        for i in range(len(nums) - 2, len(nums) - 1):
            prev, curr = nums[i - 1], nums[i]
            if prev == 0:
                continue
            if (curr - prev) / abs(prev) > threshold:
                next_prev = nums[i]
                if i + 1 < len(nums):
                    next_curr = nums[i + 1]
                    if next_prev == 0:
                        continue
                    if (next_curr - next_prev) / abs(next_prev) > threshold:
                        return True
        return False

    def _compute_overall_trend(self, points: List[TrendPoint]) -> str:
        """Use slope of the last 3 points' overall_score to determine trend."""
        recent = points[-3:] if len(points) >= 3 else points
        scores = [p.metrics.get("overall_score", 0.0) for p in recent]
        if len(scores) < 2:
            return "stable"

        slope = (scores[-1] - scores[0]) / max(len(scores) - 1, 1)
        if slope > 0.02:
            return "improving"
        if slope < -0.02:
            return "degrading"
        return "stable"
