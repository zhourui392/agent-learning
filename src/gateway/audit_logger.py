"""Audit Logger - structured tool invocation audit trail.

Records every tool call with: caller, tool, params_hash, result, latency.
Supports retrieval by trace_id / session_id and critical event alerting.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AuditEventType(Enum):
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_SUCCESS = "tool_call_success"
    TOOL_CALL_FAILURE = "tool_call_failure"
    TOOL_CALL_REJECTED = "tool_call_rejected"
    AUTH_DENIED = "auth_denied"
    CIRCUIT_OPENED = "circuit_opened"
    RATE_LIMITED = "rate_limited"
    DEGRADED = "degraded"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    event_id: str
    event_type: AuditEventType
    timestamp: float
    trace_id: str
    session_id: str
    caller_id: str
    tool_name: str
    tool_version: str = ""
    params_hash: str = ""
    result_summary: str = ""
    latency_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "caller_id": self.caller_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "params_hash": self.params_hash,
            "result_summary": self.result_summary,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


# Type alias for alert handlers
AlertHandler = Callable[[AuditEntry], None]


def _hash_params(params: Dict[str, Any]) -> str:
    """Create a deterministic hash of parameters (for audit without storing raw data)."""
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class AuditLogger:
    """Central audit logger for all tool gateway events."""

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._alert_handlers: List[AlertHandler] = []
        # Event types that trigger alerts
        self._alert_events: set = {
            AuditEventType.AUTH_DENIED,
            AuditEventType.CIRCUIT_OPENED,
            AuditEventType.TOOL_CALL_FAILURE,
        }

    def log_call_start(self, trace_id: str, session_id: str, caller_id: str,
                       tool_name: str, tool_version: str,
                       params: Dict[str, Any]) -> str:
        """Log the start of a tool call. Returns event_id for correlation."""
        entry = AuditEntry(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.TOOL_CALL_START,
            timestamp=time.time(),
            trace_id=trace_id,
            session_id=session_id,
            caller_id=caller_id,
            tool_name=tool_name,
            tool_version=tool_version,
            params_hash=_hash_params(params),
        )
        self._append(entry)
        return entry.event_id

    def log_call_success(self, trace_id: str, session_id: str, caller_id: str,
                         tool_name: str, tool_version: str,
                         result_summary: str, latency_ms: float):
        entry = AuditEntry(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.TOOL_CALL_SUCCESS,
            timestamp=time.time(),
            trace_id=trace_id,
            session_id=session_id,
            caller_id=caller_id,
            tool_name=tool_name,
            tool_version=tool_version,
            result_summary=result_summary,
            latency_ms=latency_ms,
        )
        self._append(entry)

    def log_call_failure(self, trace_id: str, session_id: str, caller_id: str,
                         tool_name: str, tool_version: str,
                         error: str, latency_ms: float):
        entry = AuditEntry(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.TOOL_CALL_FAILURE,
            timestamp=time.time(),
            trace_id=trace_id,
            session_id=session_id,
            caller_id=caller_id,
            tool_name=tool_name,
            tool_version=tool_version,
            error=error,
            latency_ms=latency_ms,
        )
        self._append(entry)

    def log_event(self, event_type: AuditEventType, trace_id: str, session_id: str,
                  caller_id: str, tool_name: str, **kwargs) -> AuditEntry:
        """Generic event logging for rejections, auth denials, etc."""
        entry = AuditEntry(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=time.time(),
            trace_id=trace_id,
            session_id=session_id,
            caller_id=caller_id,
            tool_name=tool_name,
            **kwargs,
        )
        self._append(entry)
        return entry

    def query_by_trace(self, trace_id: str) -> List[AuditEntry]:
        """Retrieve all entries for a given trace_id."""
        return [e for e in self._entries if e.trace_id == trace_id]

    def query_by_session(self, session_id: str) -> List[AuditEntry]:
        """Retrieve all entries for a given session_id."""
        return [e for e in self._entries if e.session_id == session_id]

    def query_by_tool(self, tool_name: str,
                      event_type: Optional[AuditEventType] = None) -> List[AuditEntry]:
        """Retrieve entries for a specific tool, optionally filtered by event type."""
        results = [e for e in self._entries if e.tool_name == tool_name]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return results

    def register_alert_handler(self, handler: AlertHandler):
        """Register a callback for critical events."""
        self._alert_handlers.append(handler)

    def set_alert_events(self, event_types: set):
        """Configure which event types trigger alerts."""
        self._alert_events = event_types

    @property
    def entries(self) -> List[AuditEntry]:
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _append(self, entry: AuditEntry):
        self._entries.append(entry)
        if entry.event_type in self._alert_events:
            for handler in self._alert_handlers:
                handler(entry)
