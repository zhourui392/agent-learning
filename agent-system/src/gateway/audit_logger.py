"""
Audit logger.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict


class AuditLogger:
    """
    Writes structured audit events to local file.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, log_file: Path) -> None:
        """
        Initialize audit logger.

        @param log_file: Target log file path.
        @return: None.
        """
        self._log_file = log_file
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("agent.audit")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            self._logger.addHandler(stream_handler)

    def log_step_event(
        self,
        request_id: str,
        session_id: str,
        step_id: str,
        tool_id: str,
        duration_ms: int,
        result: Dict[str, Any],
    ) -> None:
        """
        Record one step-level audit event.

        @param request_id: Request identifier.
        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param tool_id: Tool identifier.
        @param duration_ms: Step latency in milliseconds.
        @param result: Normalized tool result envelope.
        @return: None.
        """
        event = {
            "event_type": "step",
            "request_id": request_id,
            "session_id": session_id,
            "step_id": step_id,
            "tool_id": tool_id,
            "duration_ms": duration_ms,
            "result_status": "SUCCESS" if result.get("success") else "FAILED",
            "retryable": bool(result.get("retryable", False)),
            "error": result.get("error"),
        }
        self._write_event(event)
        self._logger.info(
            "step event request_id=%s session_id=%s step_id=%s tool_id=%s result=%s",
            request_id,
            session_id,
            step_id,
            tool_id,
            event["result_status"],
        )

    def log_final_event(self, request_id: str, session_id: str, success: bool, duration_ms: int) -> None:
        """
        Record one final request-level audit event.

        @param request_id: Request identifier.
        @param session_id: Session identifier.
        @param success: Final success flag.
        @param duration_ms: End-to-end latency in milliseconds.
        @return: None.
        """
        event = {
            "event_type": "final",
            "request_id": request_id,
            "session_id": session_id,
            "duration_ms": duration_ms,
            "result_status": "SUCCESS" if success else "FAILED",
        }
        self._write_event(event)
        self._logger.info(
            "final event request_id=%s session_id=%s result=%s",
            request_id,
            session_id,
            event["result_status"],
        )

    def debug(self, message: str, **fields: Any) -> None:
        """
        Emit debug-level runtime details.

        @param message: Debug message.
        @param fields: Structured fields for context.
        @return: None.
        """
        if fields:
            self._logger.debug("%s %s", message, fields)
            return
        self._logger.debug(message)

    def _write_event(self, event: Dict[str, Any]) -> None:
        """
        Append one JSON line event.

        @param event: Structured event dictionary.
        @return: None.
        """
        with self._log_file.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(event, ensure_ascii=True) + "\n")
