"""Tests for W7 arbitrator."""

from __future__ import annotations

import unittest

from src.multi_agent.arbitrator import ArbitrationCandidate, Arbitrator


class ArbitratorTestCase(unittest.TestCase):
    """Verify deterministic arbitration behavior."""

    def test_resolve_prefers_higher_priority(self) -> None:
        arbitrator = Arbitrator()
        decision = arbitrator.resolve(
            [
                ArbitrationCandidate("executor", "approve", 0.9, 2, ["e1"]),
                ArbitrationCandidate("auditor", "reject", 0.8, 1, ["e2"]),
            ]
        )

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.selected_role, "auditor")

    def test_resolve_requests_human_for_close_conflict(self) -> None:
        arbitrator = Arbitrator()
        decision = arbitrator.resolve(
            [
                ArbitrationCandidate("executor", "approve", 0.82, 2, ["e1"]),
                ArbitrationCandidate("auditor", "reject", 0.78, 2, ["e2"]),
            ]
        )

        self.assertEqual(decision.status, "needs_human")


if __name__ == "__main__":
    unittest.main()
