"""Data models for business metrics evaluation and error budget tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class BusinessMetrics:
    """Business-level evaluation metrics."""

    revenue_impact: float = 0.0
    cost_efficiency: float = 0.0
    user_satisfaction: float = 0.0


@dataclass(frozen=True)
class ErrorBudgetSnapshot:
    """Point-in-time view of an SLO error budget."""

    slo_target: float
    total_observations: int
    bad_observations: int
    burn_rate: float
    remaining: float


@dataclass(frozen=True)
class CompositeScore:
    """Combined technical + business evaluation result."""

    technical_score: float
    business_score: float
    overall_score: float
    passed: bool
    breakdown: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
