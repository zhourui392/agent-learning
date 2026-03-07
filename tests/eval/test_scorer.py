"""Unit tests for W5 evaluation scorer."""

from __future__ import annotations

import unittest

from eval.scorer import EvalCaseResult, aggregate_results, compute_f1, compute_mrr, compute_recall_at_k


class EvalScorerTestCase(unittest.TestCase):
    """Verify core scorer metrics and aggregation."""

    def test_compute_f1_returns_expected_overlap(self) -> None:
        """F1 should be positive for overlapping answers."""

        self.assertGreater(compute_f1("退款有效期30天", "退款有效期为30天"), 0.5)

    def test_recall_and_mrr_for_first_hit(self) -> None:
        """Recall and MRR should be full when first result is relevant."""

        retrieved = ["doc_a", "doc_b"]
        relevant = ["doc_a"]
        self.assertEqual(compute_recall_at_k(retrieved, relevant, 5), 1.0)
        self.assertEqual(compute_mrr(retrieved, relevant), 1.0)

    def test_aggregate_results_builds_summary(self) -> None:
        """Aggregate summary should include step rates and failure buckets."""

        case_results = [
            EvalCaseResult(
                sample_id="case-1",
                category="factual",
                difficulty="easy",
                success=True,
                answer="退款有效期30天",
                expected_answer="退款有效期30天",
                answer_f1=1.0,
                latency_ms=10.0,
                recall_at_5=1.0,
                recall_at_10=1.0,
                mrr=1.0,
                step_outcomes={"retrieval": True},
                retrieval_calls=1,
                input_tokens=3,
                output_tokens=3,
            ),
            EvalCaseResult(
                sample_id="case-2",
                category="gateway",
                difficulty="medium",
                success=False,
                answer="",
                expected_answer="PASS",
                answer_f1=0.0,
                latency_ms=20.0,
                error_code="unauthorized",
                step_outcomes={"validation": True, "authorization": False},
                auth_denied=True,
                audit_entries=1,
                input_tokens=2,
                output_tokens=0,
            ),
        ]

        summary = aggregate_results("smoke.jsonl", case_results)

        self.assertEqual(summary.total_samples, 2)
        self.assertIn("retrieval", summary.step_success_rates)
        self.assertIn("authorization", summary.step_success_rates)
        self.assertEqual(summary.failure_buckets["unauthorized"], 1)


if __name__ == "__main__":
    unittest.main()
