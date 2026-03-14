"""Cross-instance recovery -- detect orphan sessions and rebuild state."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from src.persistence.instance_registry import InstanceRegistry
from src.persistence.interfaces import SessionRecord, SessionStoreBackend


@dataclass
class RecoveryResult:
    """Outcome of one recovery sweep."""

    expired_instances: List[str]
    orphan_sessions: List[str]
    recovered_sessions: List[str]
    timestamp: float


class CrossInstanceRecovery:
    """Scan for orphan sessions left by expired instances and recover them.

    Parameters
    ----------
    session_backend : SessionStoreBackend
        Where sessions are persisted.
    instance_registry : InstanceRegistry
        Instance heartbeat tracker.
    recovery_instance_id : str
        The instance that will adopt orphan sessions.
    """

    def __init__(
        self,
        session_backend: SessionStoreBackend,
        instance_registry: InstanceRegistry,
        recovery_instance_id: str,
    ) -> None:
        self._sessions = session_backend
        self._registry = instance_registry
        self._recovery_id = recovery_instance_id

    def recover(self) -> RecoveryResult:
        """Run one recovery sweep.

        1. Detect expired instances
        2. Find sessions owned by expired instances that are still "running"
        3. Re-assign those sessions to the recovery instance
        """
        # 1. Detect expired
        expired = self._registry.detect_expired()
        expired_ids = [inst.instance_id for inst in expired]

        # 2. Find orphan sessions
        orphan_sessions: List[SessionRecord] = []
        for iid in expired_ids:
            for session in self._sessions.list_by_instance(iid):
                if session.state in ("running", "pending"):
                    orphan_sessions.append(session)

        # 3. Re-assign
        recovered_ids: List[str] = []
        now = time.time()
        for session in orphan_sessions:
            session.instance_id = self._recovery_id
            session.state = "recovered"
            session.updated_at = now
            self._sessions.put(session)
            recovered_ids.append(session.session_id)

        return RecoveryResult(
            expired_instances=expired_ids,
            orphan_sessions=[s.session_id for s in orphan_sessions],
            recovered_sessions=recovered_ids,
            timestamp=time.time(),
        )
