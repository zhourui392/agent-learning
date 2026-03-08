"""Tests for W7 multi-agent demo flows."""

from __future__ import annotations

import unittest

from src.multi_agent.demo_flow import run_conflict_flow, run_standard_flow


class DemoFlowTestCase(unittest.TestCase):
    """Verify demo flows are stable and replayable."""

    def test_run_standard_flow_returns_completed(self) -> None:
        result = run_standard_flow()
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["task"]["all_succeeded"])

    def test_run_conflict_flow_requests_human(self) -> None:
        result = run_conflict_flow()
        self.assertEqual(result["status"], "needs_human")
        self.assertTrue(result["evidence_chain"])


if __name__ == "__main__":
    unittest.main()
