"""Replay engine -- capture, store, load and replay traffic records."""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.replay.anonymizer import TrafficAnonymizer
from src.replay.models import ReplayBatch, ReplayPolicy, ReplayRecord, ReplayResult


class ReplayEngine(ABC):
    """Abstract replay engine contract."""

    @abstractmethod
    def capture(self, record: ReplayRecord) -> None:
        """Store a captured traffic record."""

    @abstractmethod
    def load_from_jsonl(self, path: str) -> int:
        """Load records from a failed-cases.jsonl file.  Return count loaded."""

    @abstractmethod
    def list_records(self, limit: int = 100) -> List[ReplayRecord]:
        """Return stored records up to *limit*."""

    @abstractmethod
    def replay(
        self,
        policy: ReplayPolicy,
        executor: Callable[[ReplayRecord], ReplayResult],
    ) -> ReplayBatch:
        """Replay stored records through *executor* according to *policy*."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored records."""


class InMemoryReplayEngine(ReplayEngine):
    """In-memory implementation of the replay engine.

    Parameters
    ----------
    anonymizer : TrafficAnonymizer, optional
        Used to strip PII on capture.  Defaults to a standard anonymizer.
    """

    def __init__(self, anonymizer: Optional[TrafficAnonymizer] = None) -> None:
        self._anonymizer = anonymizer or TrafficAnonymizer()
        self._records: List[ReplayRecord] = []

    def capture(self, record: ReplayRecord) -> None:
        if not record.anonymized:
            anon_sample = self._anonymizer.anonymize_record(record.sample)
            record = ReplayRecord(
                case_id=record.case_id,
                trace_id=record.trace_id,
                session_id=record.session_id,
                error_code=record.error_code,
                answer_f1=record.answer_f1,
                latency_ms=record.latency_ms,
                step_outcomes=dict(record.step_outcomes),
                sample=anon_sample,
                captured_at=record.captured_at or time.time(),
                anonymized=True,
            )
        self._records.append(record)

    def load_from_jsonl(self, path: str) -> int:
        count = 0
        with Path(path).open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                data = json.loads(stripped)
                record = ReplayRecord(
                    case_id=data.get("case_id", ""),
                    trace_id=data.get("trace_id"),
                    session_id=data.get("session_id"),
                    error_code=data.get("error_code"),
                    answer_f1=float(data.get("answer_f1", 0.0)),
                    latency_ms=float(data.get("latency_ms", 0.0)),
                    step_outcomes=data.get("step_outcomes", {}),
                    sample=data.get("sample", {}),
                    captured_at=data.get("captured_at"),
                    anonymized=False,
                )
                self.capture(record)
                count += 1
        return count

    def list_records(self, limit: int = 100) -> List[ReplayRecord]:
        return list(self._records[:limit])

    def replay(
        self,
        policy: ReplayPolicy,
        executor: Callable[[ReplayRecord], ReplayResult],
    ) -> ReplayBatch:
        batch_id = uuid.uuid4().hex[:12]
        sampled = self._apply_sampling(policy)
        batch = ReplayBatch(batch_id=batch_id, policy=policy, records=sampled)

        start = time.monotonic()
        for record in sampled:
            result = executor(record)
            batch.results.append(result)
        batch.total_duration_ms = (time.monotonic() - start) * 1000.0
        return batch

    def clear(self) -> None:
        self._records.clear()

    def _apply_sampling(self, policy: ReplayPolicy) -> List[ReplayRecord]:
        import random

        candidates = list(self._records)
        if policy.sample_ratio < 1.0:
            k = max(1, int(len(candidates) * policy.sample_ratio))
            candidates = random.sample(candidates, min(k, len(candidates)))
        return candidates[: policy.max_batch_size]
