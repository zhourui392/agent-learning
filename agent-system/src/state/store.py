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
    CANCELED = "CANCELED"


@dataclass
class StepState:
    """
    Runtime state for one plan step.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    step_id: str
    tool_id: str
    goal: str = ""
    depends_on: List[str] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    attempts: int = 0
    idempotency_key: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    updated_at: str = field(default_factory=lambda: _utcnow())


@dataclass
class SessionState:
    """
    Runtime state for one session.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    session_id: str
    request_id: str
    trace_id: str = ""
    plan_version: int = 1
    status: ExecutionStatus = ExecutionStatus.PENDING
    cancel_requested: bool = False
    steps: Dict[str, StepState] = field(default_factory=dict)
    step_sequence: List[str] = field(default_factory=list)
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

    def init_session(
        self,
        request_id: str,
        session_id: str,
        steps: List[Dict[str, Any]],
        plan_version: int = 1,
        trace_id: str = "",
    ) -> SessionState:
        """
        Create or update a session and register steps.

        @param request_id: External request identifier.
        @param session_id: Stable session identifier.
        @param steps: List of step dictionaries.
        @param plan_version: Current plan version.
        @param trace_id: Request trace identifier.
        @return: SessionState.
        """
        if session_id in self._sessions:
            session_state = self._sessions[session_id]
            session_state.request_id = request_id
            session_state.trace_id = trace_id or session_state.trace_id
            session_state.plan_version = max(session_state.plan_version, plan_version)
            self.upsert_plan_steps(session_id=session_id, steps=steps, plan_version=plan_version)
            self._touch_session(session_id)
            return session_state

        session_state = SessionState(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            plan_version=plan_version,
        )
        self._sessions[session_id] = session_state
        self.upsert_plan_steps(session_id=session_id, steps=steps, plan_version=plan_version)
        return session_state

    def upsert_plan_steps(self, session_id: str, steps: List[Dict[str, Any]], plan_version: int) -> None:
        """
        Insert missing steps into an existing session.

        @param session_id: Session identifier.
        @param steps: Step dictionaries from planner.
        @param plan_version: Active plan version.
        @return: None.
        """
        session_state = self.get_session(session_id)
        session_state.plan_version = max(session_state.plan_version, plan_version)

        for step in steps:
            step_id = str(step["step_id"])
            if step_id in session_state.steps:
                continue
            session_state.steps[step_id] = StepState(
                step_id=step_id,
                tool_id=str(step.get("tool_id", "")),
                goal=str(step.get("goal", "")),
                depends_on=list(step.get("depends_on", [])),
            )
            session_state.step_sequence.append(step_id)

        self._touch_session(session_id)

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
        self._touch_session(session_id)

    def mark_cancel_requested(self, session_id: str) -> None:
        """
        Mark session cancellation signal.

        @param session_id: Session identifier.
        @return: None.
        """
        session_state = self.get_session(session_id)
        session_state.cancel_requested = True
        self._touch_session(session_id)

    def is_cancel_requested(self, session_id: str) -> bool:
        """
        Check cancellation flag.

        @param session_id: Session identifier.
        @return: True when cancellation requested.
        """
        session_state = self.get_session(session_id)
        return session_state.cancel_requested

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
        step_state.updated_at = _utcnow()
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
        step_state.updated_at = _utcnow()
        self._touch_session(session_id)

    def mark_step_success(
        self,
        session_id: str,
        step_id: str,
        result: Dict[str, Any],
        idempotency_key: str,
    ) -> None:
        """
        Mark step success and persist result.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param result: Tool result payload.
        @param idempotency_key: Deterministic idempotency key.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.SUCCESS
        step_state.result = result
        step_state.error = None
        step_state.idempotency_key = idempotency_key
        step_state.updated_at = _utcnow()
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
        step_state.updated_at = _utcnow()
        self._touch_session(session_id)

    def mark_step_canceled(self, session_id: str, step_id: str, reason: Dict[str, Any]) -> None:
        """
        Mark step as canceled.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param reason: Cancellation reason.
        @return: None.
        """
        step_state = self._get_step(session_id, step_id)
        step_state.status = ExecutionStatus.CANCELED
        step_state.error = reason
        step_state.updated_at = _utcnow()
        self._touch_session(session_id)

    def should_skip_step(self, session_id: str, step_id: str, idempotency_key: str) -> bool:
        """
        Check whether a step can be skipped due to idempotent success.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param idempotency_key: Candidate idempotency key.
        @return: True when step should be skipped.
        """
        step_state = self._get_step(session_id, step_id)
        return (
            step_state.status == ExecutionStatus.SUCCESS
            and bool(step_state.idempotency_key)
            and step_state.idempotency_key == idempotency_key
        )

    def get_step_result(self, session_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """
        Get persisted step result.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @return: Step result payload.
        """
        step_state = self._get_step(session_id, step_id)
        return step_state.result

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

    def latest_snapshot_for_step(self, session_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """
        Return latest snapshot for one step.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @return: Snapshot dictionary or None.
        """
        session_state = self.get_session(session_id)
        for snapshot in reversed(session_state.snapshots):
            if snapshot.get("step_id") == step_id:
                return snapshot
        return None

    def completed_step_ids(self, session_id: str) -> List[str]:
        """
        List completed step identifiers.

        @param session_id: Session identifier.
        @return: Completed step IDs.
        """
        session_state = self.get_session(session_id)
        completed = []
        for step_id in session_state.step_sequence:
            step_state = session_state.steps[step_id]
            if step_state.status == ExecutionStatus.SUCCESS:
                completed.append(step_id)
        return completed

    def pending_step_ids(self, session_id: str) -> List[str]:
        """
        List pending or failed step identifiers.

        @param session_id: Session identifier.
        @return: Pending step IDs.
        """
        session_state = self.get_session(session_id)
        pending = []
        for step_id in session_state.step_sequence:
            step_state = session_state.steps[step_id]
            if step_state.status != ExecutionStatus.SUCCESS:
                pending.append(step_id)
        return pending

    def build_idempotency_key(self, request_id: str, step_id: str, version: int) -> str:
        """
        Build deterministic idempotency key.

        @param request_id: Request identifier.
        @param step_id: Step identifier.
        @param version: Plan version.
        @return: Idempotency key.
        """
        return f"{request_id}:{step_id}:{version}"

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
