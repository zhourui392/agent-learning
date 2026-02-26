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
    next_step_id: Optional[str]


class RecoveryService:
    """
    Calculates restart location for a failed or interrupted session.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def find_recovery_point(self, session_state: SessionState) -> RecoveryPoint:
        """
        Find next step to resume from latest persisted state.

        @param session_state: Session state object.
        @return: RecoveryPoint with completed and next step IDs.
        """
        completed_step_ids: List[str] = []
        next_step_id: Optional[str] = None

        for step_id, step_state in session_state.steps.items():
            if step_state.status == ExecutionStatus.SUCCESS:
                completed_step_ids.append(step_id)
                continue
            if next_step_id is None:
                next_step_id = step_id

        return RecoveryPoint(
            session_id=session_state.session_id,
            completed_step_ids=completed_step_ids,
            next_step_id=next_step_id,
        )
