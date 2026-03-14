"""Prometheus metrics exporter using the prometheus_client library."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover
    HAS_PROMETHEUS = False

from src.observability.exporters.interfaces import MetricsExporter


class PrometheusMetricsExporter(MetricsExporter):
    """Export metrics via prometheus_client.

    Each unique metric name creates a Prometheus instrument on first use.
    """

    def __init__(self, registry: Optional[Any] = None) -> None:
        if not HAS_PROMETHEUS:
            raise RuntimeError("prometheus_client is required: pip install prometheus_client")
        self._registry = registry or CollectorRegistry()
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}

    def counter(self, name: str, value: float = 1.0,
                labels: Optional[Dict[str, str]] = None) -> None:
        c = self._get_or_create_counter(name, labels)
        if labels:
            c.labels(**labels).inc(value)
        else:
            c.inc(value)

    def gauge(self, name: str, value: float,
              labels: Optional[Dict[str, str]] = None) -> None:
        g = self._get_or_create_gauge(name, labels)
        if labels:
            g.labels(**labels).set(value)
        else:
            g.set(value)

    def histogram(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        h = self._get_or_create_histogram(name, labels)
        if labels:
            h.labels(**labels).observe(value)
        else:
            h.observe(value)

    def snapshot(self) -> Dict[str, Any]:
        """Return raw Prometheus text exposition as a snapshot."""
        text = generate_latest(self._registry).decode("utf-8")
        return {"prometheus_text": text}

    def generate_latest(self) -> str:
        """Return Prometheus text format for /metrics endpoint."""
        return generate_latest(self._registry).decode("utf-8")

    def _get_or_create_counter(self, name: str, labels: Optional[Dict[str, str]]) -> Counter:
        if name not in self._counters:
            label_names = sorted(labels.keys()) if labels else []
            self._counters[name] = Counter(name, f"{name} counter", label_names, registry=self._registry)
        return self._counters[name]

    def _get_or_create_gauge(self, name: str, labels: Optional[Dict[str, str]]) -> Gauge:
        if name not in self._gauges:
            label_names = sorted(labels.keys()) if labels else []
            self._gauges[name] = Gauge(name, f"{name} gauge", label_names, registry=self._registry)
        return self._gauges[name]

    def _get_or_create_histogram(self, name: str, labels: Optional[Dict[str, str]]) -> Histogram:
        if name not in self._histograms:
            label_names = sorted(labels.keys()) if labels else []
            self._histograms[name] = Histogram(name, f"{name} histogram", label_names, registry=self._registry)
        return self._histograms[name]
