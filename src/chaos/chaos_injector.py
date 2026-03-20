"""Chaos injector -- inject faults into the execution path and collect results.

Scenarios can be loaded dynamically from ConfigCenter namespace
``"chaos_scenarios"``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from src.chaos.models import ChaosResult, ChaosScenario

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


class ChaosInjector(ABC):
    """Abstract chaos injection contract."""

    @abstractmethod
    def inject(self, scenario: ChaosScenario) -> None:
        """Activate a fault scenario."""

    @abstractmethod
    def remove(self, scenario: ChaosScenario) -> None:
        """Deactivate a fault scenario."""

    @abstractmethod
    def wrap_execution(
        self,
        scenario: ChaosScenario,
        fn: Callable[[], Any],
    ) -> ChaosResult:
        """Run *fn* under the given fault scenario and return the result."""

    @abstractmethod
    def collect_results(self) -> List[ChaosResult]:
        """Return all collected chaos results."""

    @abstractmethod
    def active_scenarios(self) -> List[ChaosScenario]:
        """Return currently active scenarios."""


class InMemoryChaosInjector(ChaosInjector):
    """In-memory chaos injector with simulated fault effects.

    Parameters
    ----------
    scenarios : list[ChaosScenario], optional
        Pre-loaded scenarios.
    """

    def __init__(
        self,
        scenarios: Optional[List[ChaosScenario]] = None,
    ) -> None:
        self._active: List[ChaosScenario] = []
        self._results: List[ChaosResult] = []
        self._preset_scenarios = list(scenarios) if scenarios else []

    @classmethod
    def from_config_center(
        cls,
        config_center: "ConfigCenter",
        namespace: str = "chaos_scenarios",
    ) -> "InMemoryChaosInjector":
        """Load scenarios from ConfigCenter."""
        entries = config_center.list_namespace(namespace)
        scenarios: List[ChaosScenario] = []
        for entry in entries:
            v = entry.value
            if isinstance(v, dict):
                scenarios.append(ChaosScenario(
                    fault_type=v.get("fault_type", "error"),
                    target_component=v.get("target_component", "unknown"),
                    parameters=v.get("parameters", {}),
                    duration_seconds=float(v.get("duration_seconds", 10.0)),
                    description=v.get("description", ""),
                ))
        return cls(scenarios=scenarios)

    def inject(self, scenario: ChaosScenario) -> None:
        if scenario not in self._active:
            self._active.append(scenario)

    def remove(self, scenario: ChaosScenario) -> None:
        self._active = [s for s in self._active if s is not scenario]

    def wrap_execution(
        self,
        scenario: ChaosScenario,
        fn: Callable[[], Any],
    ) -> ChaosResult:
        self.inject(scenario)
        start = time.monotonic()
        try:
            result = self._apply_fault(scenario, fn)
            recovery_ms = (time.monotonic() - start) * 1000.0
            chaos_result = ChaosResult(
                scenario=scenario,
                success=True,
                recovery_time_ms=recovery_ms,
                error_isolated=True,
                cascading_failure=False,
                metrics={"raw_result": result},
            )
        except Exception as exc:
            recovery_ms = (time.monotonic() - start) * 1000.0
            chaos_result = ChaosResult(
                scenario=scenario,
                success=False,
                recovery_time_ms=recovery_ms,
                error_isolated=False,
                cascading_failure=True,
                error=str(exc),
            )
        finally:
            self.remove(scenario)

        self._results.append(chaos_result)
        return chaos_result

    def collect_results(self) -> List[ChaosResult]:
        return list(self._results)

    def active_scenarios(self) -> List[ChaosScenario]:
        return list(self._active)

    def _apply_fault(self, scenario: ChaosScenario, fn: Callable[[], Any]) -> Any:
        """Simulate the fault type, then call the real function."""
        fault = scenario.fault_type

        if fault == "latency":
            delay = scenario.parameters.get("delay_ms", 100) / 1000.0
            time.sleep(delay)
            return fn()

        if fault == "error":
            error_rate = scenario.parameters.get("error_rate", 1.0)
            import random
            if random.random() < error_rate:
                raise RuntimeError(
                    f"Chaos injected error on {scenario.target_component}"
                )
            return fn()

        if fault == "timeout":
            timeout = scenario.parameters.get("timeout_ms", 50) / 1000.0
            time.sleep(timeout)
            raise TimeoutError(
                f"Chaos injected timeout on {scenario.target_component}"
            )

        if fault == "resource_exhaustion":
            raise MemoryError(
                f"Chaos injected resource exhaustion on {scenario.target_component}"
            )

        return fn()
