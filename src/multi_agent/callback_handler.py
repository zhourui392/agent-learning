"""Callback collection for W7 dispatched tasks."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CallbackRecord:
    """One callback result from an agent role."""

    task_id: str
    role: str
    succeeded: bool
    payload: Dict[str, Any]
    received_at: float = field(default_factory=time.time)


class CallbackHandler:
    """Collect callbacks and aggregate per-task results."""

    def __init__(self) -> None:
        self._records: Dict[str, List[CallbackRecord]] = {}

    def record(self, callback_record: CallbackRecord) -> CallbackRecord:
        """Store one callback record."""

        task_records = self._records.setdefault(callback_record.task_id, [])
        task_records.append(callback_record)
        return callback_record

    def get_task_records(self, task_id: str) -> List[CallbackRecord]:
        """Get all callbacks for one task."""

        return list(self._records.get(task_id, []))

    def aggregate_task(self, task_id: str) -> Dict[str, Any]:
        """Aggregate callback status for one task."""

        task_records = self.get_task_records(task_id)
        return {
            "task_id": task_id,
            "callback_count": len(task_records),
            "all_succeeded": bool(task_records) and all(record.succeeded for record in task_records),
            "roles": [record.role for record in task_records],
        }
