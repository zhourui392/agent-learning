"""
Snapshot builder.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from src.state.store import SessionState


@dataclass
class StepSnapshot:
    """
    Immutable snapshot for one step boundary.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    snapshot_id: str
    session_id: str
    step_id: str
    phase: str
    created_at: str
    payload: Dict[str, Any]


class SnapshotManager:
    """
    Creates normalized snapshots for replay and recovery.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def create(self, session_state: SessionState, step_id: str, phase: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a snapshot dictionary.

        @param session_state: Runtime session state.
        @param step_id: Current step identifier.
        @param phase: Snapshot phase marker.
        @param payload: Snapshot payload.
        @return: Serializable snapshot dictionary.
        """
        snapshot = StepSnapshot(
            snapshot_id=self._build_snapshot_id(session_state.session_id, step_id, len(session_state.snapshots)),
            session_id=session_state.session_id,
            step_id=step_id,
            phase=phase,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        return asdict(snapshot)

    def _build_snapshot_id(self, session_id: str, step_id: str, snapshot_index: int) -> str:
        """
        Build deterministic snapshot identifier.

        @param session_id: Session identifier.
        @param step_id: Step identifier.
        @param snapshot_index: Current snapshot index.
        @return: Snapshot ID.
        """
        return f"{session_id}:{step_id}:{snapshot_index}"
