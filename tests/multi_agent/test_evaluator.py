"""Tests for W7 multi-agent evaluator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.multi_agent.evaluator import MultiAgentEvaluator


class MultiAgentEvaluatorTestCase(unittest.TestCase):
    """Verify comparison artifacts for W7 demos."""

    def test_run_writes_summary_and_observability_outputs(self) -> None:
        evaluator = MultiAgentEvaluator()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "w7-eval"
            summary = evaluator.run(str(output_dir))

            self.assertTrue((output_dir / "summary.json").exists())
            self.assertTrue((output_dir / "report.md").exists())
            self.assertTrue((output_dir / "traces.jsonl").exists())
            self.assertTrue((output_dir / "logs.jsonl").exists())
            self.assertTrue(summary["comparison"]["conflict_requires_human"])

            payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["single_agent"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
