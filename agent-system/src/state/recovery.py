"""
Recovery service.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.state.store import ExecutionStatus, SessionState


@dataclass
class RecoveryPoint:
    """
    Recovery decision computed from session state.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    session_id: str
    completed_step_ids: List[str]
    resume_step_id: Optional[str]
    snapshot_id: Optional[str]


class RecoveryService:
    """
    Calculates restart location for a failed or interrupted session.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def find_recovery_point(
        self,
        session_state: SessionState,
        step_id: Optional[str] = None,
    ) -> RecoveryPoint:
        """
        Find next step to resume from latest persisted state.

        @param session_state: Session state object.
        @param step_id: Optional explicit recovery step.
        @return: RecoveryPoint with completed and resume step IDs.
        """
        completed_step_ids: List[str] = []
        for ordered_step_id in session_state.step_sequence:
            step_state = session_state.steps[ordered_step_id]
            if step_state.status == ExecutionStatus.SUCCESS:
                completed_step_ids.append(ordered_step_id)

        if step_id is not None:
            snapshot_id = self._find_snapshot_id(session_state=session_state, step_id=step_id)
            return RecoveryPoint(
                session_id=session_state.session_id,
                completed_step_ids=completed_step_ids,
                resume_step_id=step_id,
                snapshot_id=snapshot_id,
            )

        resume_step_id: Optional[str] = None
        for ordered_step_id in session_state.step_sequence:
            step_state = session_state.steps[ordered_step_id]
            if step_state.status != ExecutionStatus.SUCCESS:
                resume_step_id = ordered_step_id
                break

        snapshot_id = self._find_snapshot_id(session_state=session_state, step_id=resume_step_id)
        return RecoveryPoint(
            session_id=session_state.session_id,
            completed_step_ids=completed_step_ids,
            resume_step_id=resume_step_id,
            snapshot_id=snapshot_id,
        )

    def _find_snapshot_id(self, session_state: SessionState, step_id: Optional[str]) -> Optional[str]:
        """
        Locate latest snapshot ID for one step.

        @param session_state: Session state object.
        @param step_id: Step identifier.
        @return: Snapshot identifier or None.
        """
        if step_id is None:
            if not session_state.snapshots:
                return None
            return session_state.snapshots[-1].get("snapshot_id")

        for snapshot in reversed(session_state.snapshots):
            if snapshot.get("step_id") == step_id:
                return snapshot.get("snapshot_id")
        return None
