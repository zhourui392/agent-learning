"""Integration tests for W5 evaluation runner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.runner import EvaluationRunner


class EvaluationRunnerTestCase(unittest.TestCase):
    """Verify runner can execute mixed datasets and emit artifacts."""

    def test_runner_outputs_summary_and_report(self) -> None:
        """Runner should evaluate dataset and write summary/report files."""

        dataset_lines = [
            {
                "id": "smoke-rag",
                "category": "factual",
                "query": "退款政策的有效期是多少天？",
                "expected_answer": "退款有效期为30天",
                "relevant_source_ids": ["doc_refund_policy"],
                "difficulty": "easy",
            },
            {
                "id": "smoke-gateway",
                "category": "gateway",
                "query": "web search validation",
                "expected_answer": "PASS",
                "difficulty": "easy",
                "tool_name": "web_search",
                "tool_params": {"query": "refund policy"},
                "caller_role": "public",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.jsonl"
            output_dir = Path(temp_dir) / "output"
            dataset_path.write_text(
                "\n".join(json.dumps(line, ensure_ascii=False) for line in dataset_lines) + "\n",
                encoding="utf-8",
            )

            runner = EvaluationRunner(max_workers=1, timeout_seconds=5.0)
            summary = runner.run(str(dataset_path), str(output_dir))

            self.assertEqual(summary["total_samples"], 2)
            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "traces.jsonl").exists())
            self.assertTrue((output_dir / "logs.jsonl").exists())
            self.assertTrue((output_dir / "error-topn.md").exists())
            self.assertTrue((output_dir / "latency-breakdown.md").exists())
            self.assertTrue((output_dir / "alerts.json").exists())
            self.assertTrue((output_dir / "alert-report.md").exists())
            self.assertTrue((output_dir / "dashboard-snapshot.json").exists())
            self.assertTrue((output_dir / "incident-drill.md").exists())
            self.assertGreaterEqual(summary["cost"]["retrieval_calls"], 1)

    def test_runner_handles_gateway_expected_error(self) -> None:
        """Runner should treat expected gateway denial as a successful case."""

        dataset_lines = [
            {
                "id": "adv-auth",
                "category": "gateway",
                "query": "public caller probes internal tool",
                "expected_answer": "",
                "difficulty": "medium",
                "expect_error": "unauthorized",
                "tool_name": "merchant_lookup",
                "tool_params": {"merchant_id": "m-1"},
                "caller_role": "public",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.jsonl"
            output_dir = Path(temp_dir) / "output"
            dataset_path.write_text(json.dumps(dataset_lines[0], ensure_ascii=False) + "\n", encoding="utf-8")

            runner = EvaluationRunner(max_workers=1, timeout_seconds=5.0)
            summary = runner.run(str(dataset_path), str(output_dir))

            self.assertEqual(summary["e2e_success_rate"], 1.0)
            self.assertEqual(summary["failure_buckets"], {})

    def test_runner_writes_failed_case_archive(self) -> None:
        """Runner should archive failed cases for replay."""

        dataset_lines = [
            {
                "id": "rag-fail",
                "category": "factual",
                "query": "退款政策的有效期是多少天？",
                "expected_answer": "30天",
                "relevant_source_ids": ["doc_refund_policy"],
                "difficulty": "easy",
            },
            {
                "id": "gateway-pass",
                "category": "gateway",
                "query": "web search validation",
                "expected_answer": "PASS",
                "difficulty": "easy",
                "tool_name": "web_search",
                "tool_params": {"query": "refund policy"},
                "caller_role": "public",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.jsonl"
            output_dir = Path(temp_dir) / "output"
            dataset_path.write_text(
                "\n".join(json.dumps(line, ensure_ascii=False) for line in dataset_lines) + "\n",
                encoding="utf-8",
            )

            runner = EvaluationRunner(max_workers=1, timeout_seconds=5.0)
            runner.run(str(dataset_path), str(output_dir))

            archive_path = output_dir / "failed-cases.jsonl"
            records = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines() if line]

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["case_id"], "rag-fail")
            self.assertEqual(records[0]["sample"]["id"], "rag-fail")
            self.assertTrue(records[0]["trace_id"])


if __name__ == "__main__":
    unittest.main()
