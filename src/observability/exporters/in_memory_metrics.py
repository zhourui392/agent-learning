"""In-memory metrics exporter for testing and local evaluation."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.observability.exporters.interfaces import MetricsExporter


def _label_key(name: str, labels: Optional[Dict[str, str]]) -> str:
    if not labels:
        return name
    sorted_labels = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{name}{{{sorted_labels}}}"


class InMemoryMetricsExporter(MetricsExporter):
    """Stores all metrics in memory for inspection and snapshot."""

    def __init__(self) -> None:
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def counter(self, name: str, value: float = 1.0,
                labels: Optional[Dict[str, str]] = None) -> None:
        key = _label_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def gauge(self, name: str, value: float,
              labels: Optional[Dict[str, str]] = None) -> None:
        key = _label_key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def histogram(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        key = _label_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: list(v) for k, v in self._histograms.items()},
            }
