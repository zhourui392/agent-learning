"""
Execution runtime controls.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class ExecutionControl:
    """
    Runtime execution controls for timeout, cancel, and concurrency.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    max_concurrency: int = 2
    default_step_timeout_seconds: int = 8
    session_timeout_seconds: int = 60
    cancel_requested: bool = False
    started_at: float = field(default_factory=time.monotonic)

    def request_cancel(self) -> None:
        """
        Mark current execution as cancelled.

        @param self: Control object.
        @return: None.
        """
        self.cancel_requested = True

    def is_cancelled(self) -> bool:
        """
        Check whether cancellation was requested.

        @param self: Control object.
        @return: True when cancellation is active.
        """
        return self.cancel_requested

    def is_session_timed_out(self) -> bool:
        """
        Check whether session-level timeout was reached.

        @param self: Control object.
        @return: True when timeout is exceeded.
        """
        return (time.monotonic() - self.started_at) >= self.session_timeout_seconds

    @classmethod
    def from_request(cls, request: Mapping[str, Any]) -> "ExecutionControl":
        """
        Build control object from request metadata.

        @param cls: Class reference.
        @param request: Request payload.
        @return: ExecutionControl instance.
        """
        metadata = request.get("metadata", {})
        control_options = metadata.get("execution_control", {}) if isinstance(metadata, dict) else {}

        max_concurrency = int(control_options.get("max_concurrency", 2))
        step_timeout = int(control_options.get("default_step_timeout_seconds", 8))
        session_timeout = int(control_options.get("session_timeout_seconds", 60))

        if max_concurrency < 1:
            max_concurrency = 1
        if step_timeout < 1:
            step_timeout = 1
        if session_timeout < 1:
            session_timeout = 1

        return cls(
            max_concurrency=max_concurrency,
            default_step_timeout_seconds=step_timeout,
            session_timeout_seconds=session_timeout,
        )
