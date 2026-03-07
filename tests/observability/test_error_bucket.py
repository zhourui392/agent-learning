"""Unit tests for W6 error bucket analyzer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eval.scorer import EvalCaseResult
from src.observability.error_bucket import ErrorBucketAnalyzer


class ErrorBucketAnalyzerTestCase(unittest.TestCase):
    """Verify error bucket classification and report output."""

    def test_build_topn_groups_failures(self) -> None:
        """Analyzer should group failures by category and code."""

        analyzer = ErrorBucketAnalyzer()
        case_results = [
            EvalCaseResult(
                sample_id="case-1",
                category="gateway",
                difficulty="easy",
                success=False,
                answer="",
                expected_answer="PASS",
                answer_f1=0.0,
                latency_ms=10.0,
                error_code="unauthorized",
            ),
            EvalCaseResult(
                sample_id="case-2",
                category="factual",
                difficulty="easy",
                success=False,
                answer="",
                expected_answer="30天",
                answer_f1=0.2,
                latency_ms=20.0,
            ),
        ]

        topn = analyzer.build_topn(case_results)

        self.assertEqual(topn[0].error_code, "quality_regression")
        self.assertEqual(topn[1].category, "strategy")

    def test_write_markdown_report_outputs_table(self) -> None:
        """Analyzer should write Markdown report for failures."""

        analyzer = ErrorBucketAnalyzer()
        case_results = [
            EvalCaseResult(
                sample_id="case-1",
                category="gateway",
                difficulty="easy",
                success=False,
                answer="",
                expected_answer="PASS",
                answer_f1=0.0,
                latency_ms=10.0,
                error_code="tool_execution_failed",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "error-topn.md"
            analyzer.write_markdown_report(case_results, str(output_path))
            report_text = output_path.read_text(encoding="utf-8")

            self.assertIn("# Error TopN", report_text)
            self.assertIn("tool_execution_failed", report_text)


if __name__ == "__main__":
    unittest.main()
