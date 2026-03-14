"""Tests for OtlpJsonTraceExporter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.observability.exporters.otlp_trace_exporter import OtlpJsonTraceExporter


class TestOtlpJsonTraceExporter(unittest.TestCase):

    def _sample_span(self, name: str = "test-span") -> dict:
        return {
            "trace_id": "abc123",
            "session_id": "sess-1",
            "case_id": "case-1",
            "step_id": "step-1",
            "parent_step_id": None,
            "component": "planner",
            "name": name,
            "started_at_ms": 1000.0,
            "ended_at_ms": 2000.0,
            "duration_ms": 1000.0,
            "status": "ok",
        }

    def test_export_and_flush(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "traces.jsonl")
            exporter = OtlpJsonTraceExporter(path, max_buffer=100)
            exporter.export_spans([self._sample_span()])
            exporter.flush()
            lines = Path(path).read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 1)
            doc = json.loads(lines[0])
            spans = doc["resourceSpans"][0]["scopeSpans"][0]["spans"]
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0]["name"], "test-span")
            self.assertEqual(spans[0]["status"]["code"], 1)

    def test_error_span_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "traces.jsonl")
            exporter = OtlpJsonTraceExporter(path, max_buffer=100)
            span = self._sample_span()
            span["status"] = "error"
            span["error_code"] = "TimeoutError"
            exporter.export_spans([span])
            exporter.flush()
            doc = json.loads(Path(path).read_text(encoding="utf-8").strip())
            otlp_span = doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
            self.assertEqual(otlp_span["status"]["code"], 2)
            self.assertEqual(otlp_span["status"]["message"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
