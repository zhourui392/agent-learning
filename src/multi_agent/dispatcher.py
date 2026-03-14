"""Task dispatching primitives for W7 multi-agent flows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.messaging.interfaces import MessageBus


@dataclass
class TaskAssignment:
    """One assigned multi-agent task."""

    task_id: str
    role: str
    payload: Dict[str, Any]
    timeout_seconds: float = 30.0
    retry_limit: int = 1
    status: str = "pending"
    attempt_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class TaskDispatcher:
    """In-memory role-based task dispatcher.

    Optionally accepts a :class:`MessageBus` to broadcast lifecycle events.
    """

    def __init__(self, message_bus: Optional["MessageBus"] = None) -> None:
        self._assignments: Dict[str, TaskAssignment] = {}
        self._bus = message_bus

    def enqueue(self, assignment: TaskAssignment) -> TaskAssignment:
        """Register one task assignment."""

        if assignment.task_id in self._assignments:
            raise ValueError(f"task '{assignment.task_id}' already exists")
        self._assignments[assignment.task_id] = assignment
        if self._bus is not None:
            self._bus.publish(
                topic=f"task.assigned.{assignment.role}",
                payload={"task_id": assignment.task_id, "role": assignment.role},
                sender_id="dispatcher",
            )
        return assignment

    def dispatch_next(self, role: str) -> Optional[TaskAssignment]:
        """Fetch the next pending assignment for one role."""

        candidates = [
            assignment for assignment in self._assignments.values()
            if assignment.role == role and assignment.status == "pending"
        ]
        candidates.sort(key=lambda item: item.created_at)
        if not candidates:
            return None
        assignment = candidates[0]
        assignment.status = "running"
        assignment.attempt_count += 1
        assignment.updated_at = time.time()
        return assignment

    def complete(self, task_id: str, succeeded: bool) -> TaskAssignment:
        """Mark one assignment completed or failed."""

        assignment = self._get_assignment(task_id)
        assignment.status = "completed" if succeeded else "failed"
        assignment.updated_at = time.time()
        if self._bus is not None:
            self._bus.publish(
                topic="task.completed",
                payload={"task_id": task_id, "succeeded": succeeded},
                sender_id="dispatcher",
            )
        return assignment

    def recycle_timed_out(self, now: Optional[float] = None) -> List[TaskAssignment]:
        """Recycle timed-out running tasks back to pending when retry budget remains."""

        current_time = now or time.time()
        recycled: List[TaskAssignment] = []
        for assignment in self._assignments.values():
            if assignment.status != "running":
                continue
            if current_time - assignment.updated_at < assignment.timeout_seconds:
                continue
            if assignment.attempt_count > assignment.retry_limit:
                assignment.status = "failed"
                assignment.updated_at = current_time
                continue
            assignment.status = "pending"
            assignment.updated_at = current_time
            recycled.append(assignment)
        return recycled

    def list_assignments(self) -> List[TaskAssignment]:
        """Return all assignments."""

        return list(self._assignments.values())

    def _get_assignment(self, task_id: str) -> TaskAssignment:
        assignment = self._assignments.get(task_id)
        if assignment is None:
            raise ValueError(f"task '{task_id}' not found")
        return assignment
