"""OTLP-compatible JSON trace exporter."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from src.observability.exporters.interfaces import TraceExporter


class OtlpJsonTraceExporter(TraceExporter):
    """Write spans as OTLP-compatible JSON to a file.

    The output follows a simplified OpenTelemetry trace structure::

        {"resourceSpans": [{"scopeSpans": [{"spans": [...]}]}]}

    Each ``flush`` writes one such document per line (JSONL).
    """

    def __init__(self, output_path: str, max_buffer: int = 50) -> None:
        self._path = Path(output_path)
        self._buffer: List[Dict[str, Any]] = []
        self._max_buffer = max_buffer
        self._lock = threading.Lock()

    def export_spans(self, spans: List[Dict[str, Any]]) -> int:
        with self._lock:
            self._buffer.extend(spans)
            if len(self._buffer) >= self._max_buffer:
                self._flush_locked()
        return len(spans)

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        otlp_doc = {
            "resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "agent-system"}}]},
                "scopeSpans": [{
                    "scope": {"name": "agent-tracer"},
                    "spans": [self._to_otlp_span(s) for s in self._buffer],
                }],
            }],
        }
        with self._path.open("a", encoding="utf-8") as fh:
            json.dump(otlp_doc, fh, ensure_ascii=False, default=str)
            fh.write("\n")
        self._buffer.clear()

    @staticmethod
    def _to_otlp_span(span: Dict[str, Any]) -> Dict[str, Any]:
        """Convert an internal span dict to OTLP span format."""
        return {
            "traceId": span.get("trace_id", ""),
            "spanId": span.get("step_id", ""),
            "parentSpanId": span.get("parent_step_id", ""),
            "name": span.get("name", ""),
            "kind": 1,  # INTERNAL
            "startTimeUnixNano": int(span.get("started_at_ms", 0) * 1_000_000),
            "endTimeUnixNano": int(span.get("ended_at_ms", 0) * 1_000_000),
            "status": {
                "code": 1 if span.get("status") == "ok" else 2,
                "message": span.get("error_code", ""),
            },
            "attributes": [
                {"key": "component", "value": {"stringValue": span.get("component", "")}},
                {"key": "session_id", "value": {"stringValue": span.get("session_id", "")}},
            ],
        }
