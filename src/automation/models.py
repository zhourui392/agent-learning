"""Data models for the automated regression pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.chaos.models import ChaosScenario


@dataclass
class RegressionRunConfig:
    """Configuration for a single regression run."""

    run_id: str
    dataset_path: str
    experiment_id: str = ""
    chaos_scenarios: List[ChaosScenario] = field(default_factory=list)
    enable_replay: bool = True
    enable_chaos: bool = True
    enable_ab_routing: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateDecision:
    """Result of the automated release gate evaluation."""

    passed: bool
    reasons: List[str] = field(default_factory=list)
    blocking_alerts: int = 0
    budget_ok: bool = True
    score_ok: bool = True


@dataclass
class RegressionRunResult:
    """Full result of an automated regression run."""

    run_id: str
    config: RegressionRunConfig
    gate_decision: GateDecision
    summary: Dict[str, Any] = field(default_factory=dict)
    composite_score: Optional[Any] = None
    resilience_report: Optional[Any] = None
    replay_batch_id: Optional[str] = None
    steps_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None
