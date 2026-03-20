"""Data models for ops reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TrendPoint:
    """One data point in a trend series."""

    run_id: str
    metrics: Dict[str, float] = field(default_factory=dict)
    gate_passed: bool = True
    timestamp: float = 0.0


@dataclass
class TrendAnalysis:
    """Result of trend analysis across multiple runs."""

    regressions: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    overall_trend: str = "stable"  # improving | stable | degrading


@dataclass
class WeeklyReportData:
    """Aggregated data for a weekly ops report."""

    period_start: str
    period_end: str
    total_runs: int = 0
    gate_pass_rate: float = 0.0
    avg_overall_score: float = 0.0
    trend: TrendAnalysis = field(default_factory=TrendAnalysis)
    points: List[TrendPoint] = field(default_factory=list)
