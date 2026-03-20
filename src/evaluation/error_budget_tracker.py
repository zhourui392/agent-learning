"""Error budget tracker -- SLO burn-rate accounting.

Reads ``slo_target`` from ConfigCenter namespace ``"slo_targets"`` when
constructed via ``from_config_center()``.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from src.evaluation.models import ErrorBudgetSnapshot

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


class ErrorBudgetTracker:
    """Track SLO error budget consumption over a series of observations.

    Parameters
    ----------
    slo_target : float
        Target success rate, e.g. 0.995 for 99.5 %.
    """

    def __init__(self, slo_target: float = 0.995) -> None:
        if not 0.0 < slo_target <= 1.0:
            raise ValueError(f"slo_target must be in (0, 1], got {slo_target}")
        self._slo_target = slo_target
        self._total: int = 0
        self._bad: int = 0

    @classmethod
    def from_config_center(
        cls,
        config_center: "ConfigCenter",
        namespace: str = "slo_targets",
        key: str = "default",
    ) -> "ErrorBudgetTracker":
        """Create a tracker whose SLO target comes from ConfigCenter."""
        entry = config_center.get(namespace, key)
        target = float(entry.value) if entry is not None else 0.995
        return cls(slo_target=target)

    def record(self, success: bool) -> None:
        """Record one observation."""
        self._total += 1
        if not success:
            self._bad += 1

    def record_batch(self, total: int, bad: int) -> None:
        """Record a batch of observations at once."""
        self._total += total
        self._bad += bad

    def snapshot(self) -> ErrorBudgetSnapshot:
        """Return the current budget state."""
        if self._total == 0:
            return ErrorBudgetSnapshot(
                slo_target=self._slo_target,
                total_observations=0,
                bad_observations=0,
                burn_rate=0.0,
                remaining=1.0,
            )

        allowed_bad = self._total * (1.0 - self._slo_target)
        burn_rate = self._bad / allowed_bad if allowed_bad > 0 else float("inf")
        remaining = max(0.0, 1.0 - burn_rate)

        return ErrorBudgetSnapshot(
            slo_target=self._slo_target,
            total_observations=self._total,
            bad_observations=self._bad,
            burn_rate=round(burn_rate, 4),
            remaining=round(remaining, 4),
        )

    def is_budget_exhausted(self) -> bool:
        """Return ``True`` when the error budget is fully consumed."""
        snap = self.snapshot()
        return snap.remaining <= 0.0

    def reset(self) -> None:
        """Reset observations (e.g. start of a new budget window)."""
        self._total = 0
        self._bad = 0
