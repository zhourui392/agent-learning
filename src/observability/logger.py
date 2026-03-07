"""Structured logger for W6 observability."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.observability.tracer import TraceContext


@dataclass
class StructuredLogEntry:
    """One structured log entry."""

    timestamp_ms: float
    level: str
    event_type: str
    component: str
    message: str
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    case_id: Optional[str] = None
    step_id: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dict."""

        return asdict(self)


class StructuredLogger:
    """In-memory structured logger."""

    def __init__(self) -> None:
        self._entries: List[StructuredLogEntry] = []
        self._lock = threading.Lock()

    def info(
        self,
        component: str,
        event_type: str,
        message: str,
        trace_context: Optional[TraceContext] = None,
        step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record one info log entry."""

        self._append("INFO", component, event_type, message, trace_context, step_id, None, metadata)

    def warning(
        self,
        component: str,
        event_type: str,
        message: str,
        trace_context: Optional[TraceContext] = None,
        step_id: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record one warning log entry."""

        self._append("WARN", component, event_type, message, trace_context, step_id, error_code, metadata)

    def error(
        self,
        component: str,
        event_type: str,
        message: str,
        trace_context: Optional[TraceContext] = None,
        step_id: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record one error log entry."""

        self._append("ERROR", component, event_type, message, trace_context, step_id, error_code, metadata)

    def list_entries(self) -> List[StructuredLogEntry]:
        """Return a snapshot of log entries."""

        with self._lock:
            return list(self._entries)

    def write_jsonl(self, output_path: str) -> None:
        """Persist logs as JSONL."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as file_handle:
            for entry in self.list_entries():
                json.dump(entry.to_dict(), file_handle, ensure_ascii=False)
                file_handle.write("\n")

    def _append(
        self,
        level: str,
        component: str,
        event_type: str,
        message: str,
        trace_context: Optional[TraceContext],
        step_id: Optional[str],
        error_code: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        entry = StructuredLogEntry(
            timestamp_ms=time.time() * 1000,
            level=level,
            event_type=event_type,
            component=component,
            message=message,
            trace_id=trace_context.trace_id if trace_context else None,
            session_id=trace_context.session_id if trace_context else None,
            case_id=trace_context.case_id if trace_context else None,
            step_id=step_id,
            error_code=error_code,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._entries.append(entry)
