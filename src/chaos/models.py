"""Data models for the chaos injection subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ChaosScenario:
    """Definition of one fault injection scenario."""

    fault_type: str  # latency | error | timeout | resource_exhaustion
    target_component: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 10.0
    description: str = ""


@dataclass
class ChaosResult:
    """Outcome of executing under one chaos scenario."""

    scenario: ChaosScenario
    success: bool
    recovery_time_ms: float = 0.0
    error_isolated: bool = True
    cascading_failure: bool = False
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ResilienceReport:
    """Aggregated resilience assessment across all chaos scenarios."""

    overall_score: float
    scenario_scores: Dict[str, float] = field(default_factory=dict)
    weaknesses: List[str] = field(default_factory=list)
    details: List[ChaosResult] = field(default_factory=list)
