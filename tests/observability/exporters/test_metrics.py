"""Tests for MetricsExporter implementations."""

from __future__ import annotations

import unittest

from src.observability.exporters.in_memory_metrics import InMemoryMetricsExporter
from src.observability.exporters.prometheus_exporter import PrometheusMetricsExporter


class TestInMemoryMetricsExporter(unittest.TestCase):

    def setUp(self):
        self.exporter = InMemoryMetricsExporter()

    def test_counter_basic(self):
        self.exporter.counter("requests_total")
        self.exporter.counter("requests_total", 2.0)
        snap = self.exporter.snapshot()
        self.assertEqual(snap["counters"]["requests_total"], 3.0)

    def test_counter_with_labels(self):
        self.exporter.counter("http_requests", labels={"method": "GET"})
        self.exporter.counter("http_requests", labels={"method": "POST"})
        snap = self.exporter.snapshot()
        self.assertEqual(snap["counters"]["http_requests{method=GET}"], 1.0)
        self.assertEqual(snap["counters"]["http_requests{method=POST}"], 1.0)

    def test_gauge(self):
        self.exporter.gauge("cpu_usage", 0.75)
        self.exporter.gauge("cpu_usage", 0.80)
        snap = self.exporter.snapshot()
        self.assertEqual(snap["gauges"]["cpu_usage"], 0.80)

    def test_histogram(self):
        self.exporter.histogram("latency_ms", 10.0)
        self.exporter.histogram("latency_ms", 20.0)
        self.exporter.histogram("latency_ms", 30.0)
        snap = self.exporter.snapshot()
        self.assertEqual(snap["histograms"]["latency_ms"], [10.0, 20.0, 30.0])

    def test_empty_snapshot(self):
        snap = self.exporter.snapshot()
        self.assertEqual(snap["counters"], {})
        self.assertEqual(snap["gauges"], {})
        self.assertEqual(snap["histograms"], {})


class TestPrometheusMetricsExporter(unittest.TestCase):

    def test_counter_and_generate(self):
        exporter = PrometheusMetricsExporter()
        exporter.counter("test_requests_total", 5.0)
        text = exporter.generate_latest()
        self.assertIn("test_requests_total", text)

    def test_gauge_and_snapshot(self):
        exporter = PrometheusMetricsExporter()
        exporter.gauge("test_temperature", 36.6)
        snap = exporter.snapshot()
        self.assertIn("test_temperature", snap["prometheus_text"])

    def test_histogram(self):
        exporter = PrometheusMetricsExporter()
        exporter.histogram("test_duration_seconds", 0.5)
        exporter.histogram("test_duration_seconds", 1.2)
        text = exporter.generate_latest()
        self.assertIn("test_duration_seconds", text)


if __name__ == "__main__":
    unittest.main()
