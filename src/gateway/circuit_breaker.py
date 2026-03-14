"""Circuit Breaker - per-tool failure isolation with half-open recovery.

States:
    CLOSED  -> normal operation, failures are counted
    OPEN    -> all calls rejected, waiting for recovery timeout
    HALF_OPEN -> allow one probe call to test recovery

W9 update: constructor accepts an optional ``CircuitStateBackend`` for
persistent storage.  State changes are automatically persisted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from src.persistence.interfaces import CircuitRecord, CircuitStateBackend


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker instance."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 30.0      # Seconds before trying half-open
    success_threshold: int = 2          # Successes in half-open before closing
    window_size: float = 60.0           # Sliding window for failure counting


@dataclass
class CircuitStats:
    """Runtime statistics for a circuit."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    half_open_successes: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    total_calls: int = 0
    total_failures: int = 0
    total_rejections: int = 0


class CircuitBreaker:
    """Per-tool circuit breaker with three-state model.

    Parameters
    ----------
    config : CircuitConfig, optional
        Tuning knobs.
    backend : CircuitStateBackend, optional
        When supplied, every state mutation is persisted so that a new
        ``CircuitBreaker`` instance can resume from the same state.
    """

    def __init__(
        self,
        config: Optional[CircuitConfig] = None,
        backend: Optional[CircuitStateBackend] = None,
    ):
        self._config = config or CircuitConfig()
        self._backend = backend
        # {tool_name: CircuitStats}
        self._circuits: Dict[str, CircuitStats] = {}

    def get_state(self, tool_name: str) -> CircuitState:
        stats = self._get_stats(tool_name)
        self._maybe_transition_to_half_open(tool_name, stats)
        return stats.state

    def get_stats(self, tool_name: str) -> CircuitStats:
        stats = self._get_stats(tool_name)
        self._maybe_transition_to_half_open(tool_name, stats)
        return stats

    def allow_request(self, tool_name: str) -> bool:
        """Check if a request should be allowed through."""
        stats = self._get_stats(tool_name)
        self._maybe_transition_to_half_open(tool_name, stats)

        if stats.state == CircuitState.CLOSED:
            return True

        if stats.state == CircuitState.HALF_OPEN:
            return True  # Allow probe calls

        # OPEN
        stats.total_rejections += 1
        self._persist(tool_name, stats)
        return False

    def record_success(self, tool_name: str):
        """Record a successful tool call."""
        stats = self._get_stats(tool_name)
        stats.total_calls += 1
        stats.success_count += 1

        if stats.state == CircuitState.HALF_OPEN:
            stats.half_open_successes += 1
            if stats.half_open_successes >= self._config.success_threshold:
                self._transition(stats, CircuitState.CLOSED)
        elif stats.state == CircuitState.CLOSED:
            # Reset failure count on success
            stats.failure_count = 0

        self._persist(tool_name, stats)

    def record_failure(self, tool_name: str):
        """Record a failed tool call."""
        stats = self._get_stats(tool_name)
        stats.total_calls += 1
        stats.total_failures += 1
        stats.failure_count += 1
        stats.last_failure_time = time.time()

        if stats.state == CircuitState.HALF_OPEN:
            # Probe failed, go back to open
            self._transition(stats, CircuitState.OPEN)
        elif stats.state == CircuitState.CLOSED:
            if stats.failure_count >= self._config.failure_threshold:
                self._transition(stats, CircuitState.OPEN)

        self._persist(tool_name, stats)

    def reset(self, tool_name: str):
        """Manually reset a circuit to closed state."""
        if tool_name in self._circuits:
            self._transition(self._circuits[tool_name], CircuitState.CLOSED)
            self._persist(tool_name, self._circuits[tool_name])

    def _get_stats(self, tool_name: str) -> CircuitStats:
        if tool_name not in self._circuits:
            # Try loading from backend first
            if self._backend is not None:
                rec = self._backend.get(tool_name)
                if rec is not None:
                    self._circuits[tool_name] = CircuitStats(
                        state=CircuitState(rec.state),
                        failure_count=rec.failure_count,
                        success_count=rec.success_count,
                        half_open_successes=rec.half_open_successes,
                        last_failure_time=rec.last_failure_time,
                        last_state_change=rec.last_state_change,
                        total_calls=rec.total_calls,
                        total_failures=rec.total_failures,
                        total_rejections=rec.total_rejections,
                    )
                    return self._circuits[tool_name]
            self._circuits[tool_name] = CircuitStats()
        return self._circuits[tool_name]

    def _persist(self, tool_name: str, stats: CircuitStats) -> None:
        """Write current stats to the backend if one is configured."""
        if self._backend is None:
            return
        self._backend.put(CircuitRecord(
            tool_name=tool_name,
            state=stats.state.value,
            failure_count=stats.failure_count,
            success_count=stats.success_count,
            half_open_successes=stats.half_open_successes,
            last_failure_time=stats.last_failure_time,
            last_state_change=stats.last_state_change,
            total_calls=stats.total_calls,
            total_failures=stats.total_failures,
            total_rejections=stats.total_rejections,
        ))

    def _maybe_transition_to_half_open(self, tool_name: str, stats: CircuitStats):
        """Auto-transition from OPEN to HALF_OPEN after recovery timeout."""
        if stats.state != CircuitState.OPEN:
            return
        elapsed = time.time() - stats.last_state_change
        if elapsed >= self._config.recovery_timeout:
            self._transition(stats, CircuitState.HALF_OPEN)
            self._persist(tool_name, stats)

    def _transition(self, stats: CircuitStats, new_state: CircuitState):
        stats.state = new_state
        stats.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            stats.failure_count = 0
            stats.half_open_successes = 0
        elif new_state == CircuitState.HALF_OPEN:
            stats.half_open_successes = 0
