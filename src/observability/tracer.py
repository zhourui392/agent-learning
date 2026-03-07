"""Trace and span primitives for W6 observability."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TraceContext:
    """Minimal trace context shared across one request chain."""

    trace_id: str
    session_id: str
    case_id: str
    tags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanRecord:
    """One completed span record."""

    trace_id: str
    session_id: str
    case_id: str
    step_id: str
    parent_step_id: Optional[str]
    component: str
    name: str
    started_at_ms: float
    ended_at_ms: float
    duration_ms: float
    status: str
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to JSON-serializable dict."""

        return asdict(self)


class SpanScope:
    """Context manager that completes a span on exit."""

    def __init__(
        self,
        tracer: "Tracer",
        trace_context: TraceContext,
        component: str,
        name: str,
        parent_step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.step_id = f"step-{uuid.uuid4().hex[:8]}"
        self._tracer = tracer
        self._trace_context = trace_context
        self._component = component
        self._name = name
        self._parent_step_id = parent_step_id
        self._metadata = dict(metadata or {})
        self._started_at_ms = 0.0
        self._closed = False

    def __enter__(self) -> "SpanScope":
        self._started_at_ms = time.time() * 1000
        return self

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> None:
        if self._closed:
            return
        if exc is None:
            self.finish()
            return
        self.finish(status="error", error_code=exc.__class__.__name__)

    def finish(
        self,
        status: str = "ok",
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SpanRecord:
        """Complete one span and persist it in tracer."""

        if self._closed:
            raise RuntimeError("span already closed")
        self._closed = True
        ended_at_ms = time.time() * 1000
        merged_metadata = dict(self._metadata)
        merged_metadata.update(metadata or {})
        span_record = SpanRecord(
            trace_id=self._trace_context.trace_id,
            session_id=self._trace_context.session_id,
            case_id=self._trace_context.case_id,
            step_id=self.step_id,
            parent_step_id=self._parent_step_id,
            component=self._component,
            name=self._name,
            started_at_ms=self._started_at_ms,
            ended_at_ms=ended_at_ms,
            duration_ms=max(0.0, ended_at_ms - self._started_at_ms),
            status=status,
            error_code=error_code,
            metadata=merged_metadata,
        )
        self._tracer.record(span_record)
        return span_record


class Tracer:
    """In-memory tracer used by the evaluation runner."""

    def __init__(self) -> None:
        self._spans: List[SpanRecord] = []
        self._lock = threading.Lock()

    def start_span(
        self,
        trace_context: TraceContext,
        component: str,
        name: str,
        parent_step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SpanScope:
        """Create one span scope."""

        return SpanScope(self, trace_context, component, name, parent_step_id, metadata)

    def record(self, span_record: SpanRecord) -> None:
        """Append one completed span."""

        with self._lock:
            self._spans.append(span_record)

    def list_spans(self) -> List[SpanRecord]:
        """Return a snapshot of collected spans."""

        with self._lock:
            return list(self._spans)

    def write_jsonl(self, output_path: str) -> None:
        """Persist spans as JSONL."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as file_handle:
            for span_record in self.list_spans():
                json.dump(span_record.to_dict(), file_handle, ensure_ascii=False)
                file_handle.write("\n")
