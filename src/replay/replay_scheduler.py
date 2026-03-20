"""Replay scheduler -- schedules replay batches via TaskQueue.

Reads replay policy from ConfigCenter namespace ``"replay_policy"``.
"""

from __future__ import annotations

import json
import uuid
from typing import Optional, TYPE_CHECKING

from src.replay.models import ReplayPolicy

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter
    from src.scheduler.interfaces import TaskQueue


_REPLAY_QUEUE = "replay_tasks"


class ReplayScheduler:
    """Schedule replay batches through a distributed TaskQueue.

    Parameters
    ----------
    task_queue : TaskQueue
        Queue backend for distributing replay work.
    config_center : ConfigCenter, optional
        Used to read dynamic replay policy from namespace ``"replay_policy"``.
    default_policy : ReplayPolicy, optional
        Fallback when ConfigCenter has no policy entry.
    """

    def __init__(
        self,
        task_queue: "TaskQueue",
        config_center: Optional["ConfigCenter"] = None,
        default_policy: Optional[ReplayPolicy] = None,
    ) -> None:
        self._queue = task_queue
        self._config_center = config_center
        self._default_policy = default_policy or ReplayPolicy()

    def current_policy(self) -> ReplayPolicy:
        """Resolve the active replay policy (ConfigCenter > default)."""
        if self._config_center is not None:
            entry = self._config_center.get("replay_policy", "default")
            if entry is not None and isinstance(entry.value, dict):
                v = entry.value
                return ReplayPolicy(
                    throttle_rate=float(v.get("throttle_rate", self._default_policy.throttle_rate)),
                    sample_ratio=float(v.get("sample_ratio", self._default_policy.sample_ratio)),
                    target_variant=v.get("target_variant", self._default_policy.target_variant),
                    max_batch_size=int(v.get("max_batch_size", self._default_policy.max_batch_size)),
                )
        return self._default_policy

    def schedule(self, dataset_path: str, run_id: Optional[str] = None) -> str:
        """Enqueue a replay task.  Return the task_id."""
        from src.scheduler.interfaces import TaskItem

        task_id = run_id or uuid.uuid4().hex[:12]
        policy = self.current_policy()
        payload = {
            "action": "replay",
            "dataset_path": dataset_path,
            "policy": {
                "throttle_rate": policy.throttle_rate,
                "sample_ratio": policy.sample_ratio,
                "target_variant": policy.target_variant,
                "max_batch_size": policy.max_batch_size,
            },
        }
        item = TaskItem(
            task_id=task_id,
            queue_name=_REPLAY_QUEUE,
            payload=payload,
        )
        self._queue.enqueue(item)
        return task_id

    def pending_count(self) -> int:
        """Return the number of pending replay tasks."""
        return self._queue.queue_length(_REPLAY_QUEUE)
