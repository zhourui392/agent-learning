"""Unit tests for W6 latency analyzer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eval.scorer import EvalCaseResult
from src.observability.latency_analyzer import LatencyAnalyzer
from src.observability.tracer import SpanRecord


class LatencyAnalyzerTestCase(unittest.TestCase):
    """Verify latency hotspot analysis."""

    def test_build_hotspots_ranks_by_p95(self) -> None:
        """Hotspots should be ordered by higher P95 duration."""

        analyzer = LatencyAnalyzer()
        spans = [
            SpanRecord("t1", "s1", "c1", "step-1", None, "retrieval", "retrieve", 0, 30, 30, "ok"),
            SpanRecord("t1", "s1", "c1", "step-2", None, "rerank", "rerank", 0, 80, 80, "ok"),
        ]

        hotspots = analyzer.build_hotspots(spans)

        self.assertEqual(hotspots[0].component, "rerank")

    def test_write_markdown_report_outputs_summary(self) -> None:
        """Analyzer should write latency report."""

        analyzer = LatencyAnalyzer()
        case_results = [
            EvalCaseResult(
                sample_id="case-1",
                category="factual",
                difficulty="easy",
                success=True,
                answer="ok",
                expected_answer="ok",
                answer_f1=1.0,
                latency_ms=40.0,
            )
        ]
        spans = [
            SpanRecord("t1", "s1", "c1", "step-1", None, "retrieval", "retrieve", 0, 30, 30, "ok")
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latency-breakdown.md"
            analyzer.write_markdown_report(case_results, spans, str(output_path))
            report_text = output_path.read_text(encoding="utf-8")

            self.assertIn("# Latency Breakdown", report_text)
            self.assertIn("retrieval", report_text)


if __name__ == "__main__":
    unittest.main()
