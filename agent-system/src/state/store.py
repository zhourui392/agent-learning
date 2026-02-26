"""
Session state store.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(str, Enum):
    """
    Session and step execution status.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_TOOL = "WAITING_TOOL"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class StepState:
    """
    Runtime state for one plan step.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    step_id: str
    tool_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    attempts: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


@dataclass
class SessionState:
    """
    Runtime state for one session.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    session_id: str
    request_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: Dict[str, StepState] = field(default_factory=dict)
    snapshots: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _utcnow())
    updated_at: str = field(default_factory=lambda: _utcnow())


class InMemoryStateStore:
    """
    In-memory store used for local run and tests.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self) -> None:
        """
        Initialize empty store.

        @param self: Store instance.
        @return: None.
        """
        self._sessions: Dict[str, SessionState] = {}

    def init_session(self, request_id: str, session_id: str, steps: List[Dict[str, str]]) -> SessionState:
        """
        Create a new session and pre-register steps.

        @param request_id: External request identifier.
        @param session_id: Stable session identifier.
        @param steps: List of dictionaries with step_id and tool_id.
        @return: Created SessionState.
        """
        session_state = SessionState(session_id=session_id, request_id=request_id)
        for step in steps:
            session_state.steps[step["step_id"]] = StepState(step_id=step["step_id"], tool_id=step["tool_id"])
        self._sessions[session_id] = session_state
        return session_state

    def get_session(self, session_id: str) -> SessionState:
        """
        Fetch session state by ID.

        @param session_id: Session identifier.
        @return: SessionState object.
        """
        if session_id not in self._sessions:
            raise KeyError(f"session not found: {session_id}")
        return self._sessions[session_id]

    def set_session_status(self, session_id: str, status: ExecutionStatus) -> None:
        """
        Update top-level session status.

        @param session_id: Session identifier.
        @param status: New session status.
        @return: None.
        """
        session_state = self.get_session(session_id)
        session_state.status = status
        session_state.updated_at = _utcnow()

    def mark_step_running(self, session_id: str, step_id: str) -> None:
        """
        Mark a step as running and increase attempts.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.RUNNING
        step_state.attempts += 1
        self._touch_session(session_id)

    def mark_step_waiting_tool(self, session_id: str, step_id: str) -> None:
        """
        Mark a step as waiting for tool result.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.WAITING_TOOL
        self._touch_session(session_id)

    def mark_step_success(self, session_id: str, step_id: str, result: Dict[str, Any]) -> None:
        """
        Mark step success and persist result.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param result: Tool result payload.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.SUCCESS
        step_state.result = result
        step_state.error = None
        self._touch_session(session_id)

    def mark_step_failed(self, session_id: str, step_id: str, error: Dict[str, Any]) -> None:
        """
        Mark step failure and persist error.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param error: Error payload.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.FAILED
        step_state.error = error
        self._touch_session(session_id)

    def save_snapshot(self, session_id: str, snapshot: Dict[str, Any]) -> None:
        """
        Append a snapshot to session history.

        @param session_id: Session identifier.
        @param snapshot: Snapshot dictionary.
        @return: None.
        """
        session_state = self.get_session(session_id)
        session_state.snapshots.append(snapshot)
        self._touch_session(session_id)

    def latest_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the latest snapshot or None.

        @param session_id: Session identifier.
        @return: Latest snapshot dictionary.
        """
        session_state = self.get_session(session_id)
        if not session_state.snapshots:
            return None
        return session_state.snapshots[-1]

    def completed_step_ids(self, session_id: str) -> List[str]:
        """
        List completed step identifiers.

        @param session_id: Session identifier.
        @return: Completed step IDs.
        """
        session_state = self.get_session(session_id)
        completed = []
        for step_id, step_state in session_state.steps.items():
            if step_state.status == ExecutionStatus.SUCCESS:
                completed.append(step_id)
        return completed

    def _get_step(self, session_id: str, step_id: str) -> StepState:
        """
        Lookup step state by session and step identifiers.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @return: StepState object.
        """
        session_state = self.get_session(session_id)
        if step_id not in session_state.steps:
            raise KeyError(f"step not found: {step_id}")
        return session_state.steps[step_id]

    def _touch_session(self, session_id: str) -> None:
        """
        Update session modification timestamp.

        @param session_id: Session identifier.
        @return: None.
        """
        session_state = self.get_session(session_id)
        session_state.updated_at = _utcnow()


def _utcnow() -> str:
    """
    Generate UTC timestamp in ISO format.

    @param: None.
    @return: UTC timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()
