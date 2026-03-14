"""Abstract exporter interfaces for metrics, logs and traces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MetricsExporter(ABC):
    """Export numeric metrics (counters, gauges, histograms)."""

    @abstractmethod
    def counter(self, name: str, value: float = 1.0,
                labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""

    @abstractmethod
    def gauge(self, name: str, value: float,
              labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value."""

    @abstractmethod
    def histogram(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation."""

    @abstractmethod
    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""


class LogExporter(ABC):
    """Export structured log entries."""

    @abstractmethod
    def export(self, entries: List[Dict[str, Any]]) -> int:
        """Export log entries.  Return the count of entries exported."""

    @abstractmethod
    def flush(self) -> None:
        """Force-flush any buffered entries."""


class TraceExporter(ABC):
    """Export trace spans."""

    @abstractmethod
    def export_spans(self, spans: List[Dict[str, Any]]) -> int:
        """Export span dicts.  Return the count exported."""

    @abstractmethod
    def flush(self) -> None:
        """Force-flush any buffered spans."""
