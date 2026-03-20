"""Data models for the traffic replay subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReplayRecord:
    """One captured traffic record, compatible with failed-cases.jsonl format."""

    case_id: str
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    error_code: Optional[str] = None
    answer_f1: float = 0.0
    latency_ms: float = 0.0
    step_outcomes: Dict[str, bool] = field(default_factory=dict)
    sample: Dict[str, Any] = field(default_factory=dict)
    captured_at: Optional[float] = None
    anonymized: bool = False


@dataclass(frozen=True)
class ReplayPolicy:
    """Controls how traffic is replayed."""

    throttle_rate: float = 1.0
    sample_ratio: float = 1.0
    target_variant: str = "control"
    max_batch_size: int = 50


@dataclass
class ReplayResult:
    """Outcome of replaying a single record."""

    record_id: str
    success: bool
    latency_ms: float = 0.0
    error: Optional[str] = None
    variant: str = "control"
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayBatch:
    """A batch of replay results."""

    batch_id: str
    policy: ReplayPolicy
    records: List[ReplayRecord] = field(default_factory=list)
    results: List[ReplayResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
