"""W5 evaluation scoring utilities."""

from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EvalSample:
    """Evaluation sample definition."""

    id: str
    category: str
    query: str
    expected_answer: str
    relevant_source_ids: List[str] = field(default_factory=list)
    difficulty: str = "medium"
    tags: List[str] = field(default_factory=list)
    expect_error: Optional[str] = None
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    caller_role: str = "public"
    tenant: str = "default"


@dataclass
class EvalCaseResult:
    """Per-sample evaluation result."""

    sample_id: str
    category: str
    difficulty: str
    success: bool
    answer: str
    expected_answer: str
    answer_f1: float
    latency_ms: float
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    retrieved_source_ids: List[str] = field(default_factory=list)
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr: float = 0.0
    error_code: Optional[str] = None
    step_outcomes: Dict[str, bool] = field(default_factory=dict)
    validation_rejected: bool = False
    auth_denied: bool = False
    circuit_opened: bool = False
    audit_entries: int = 0
    retrieval_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class EvalSummary:
    """Aggregated evaluation summary."""

    dataset_name: str
    total_samples: int
    e2e_success_rate: float
    step_success_rates: Dict[str, float]
    p95_latency_ms: float
    avg_latency_ms: float
    avg_recall_at_5: float
    avg_recall_at_10: float
    avg_mrr: float
    avg_answer_f1: float
    accuracy: float
    consistency_std: float
    stability: float
    validation_rejection_rate: float
    auth_denial_rate: float
    circuit_open_frequency: float
    audit_completeness: float
    cost: Dict[str, int]
    failure_buckets: Dict[str, int]
    by_category: Dict[str, Dict[str, float]]
    by_difficulty: Dict[str, Dict[str, float]]
    details: List[EvalCaseResult]

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to JSON-serializable dict."""

        payload = asdict(self)
        payload["details"] = [asdict(detail) for detail in self.details]
        return payload


def load_samples(dataset_path: str) -> List[EvalSample]:
    """Load evaluation samples from a JSONL file."""

    samples: List[EvalSample] = []
    with Path(dataset_path).open("r", encoding="utf-8") as file_handle:
        for raw_line in file_handle:
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue
            sample_data = json.loads(stripped_line)
            samples.append(EvalSample(**sample_data))
    return samples


def tokenize_text(text: str) -> List[str]:
    """Tokenize text with simple CJK-aware pattern."""

    normalized_text = text.lower().strip()
    raw_tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized_text)
    return [token for token in raw_tokens if token]


def estimate_tokens(text: str) -> int:
    """Estimate token count for cost tracking."""

    return len(tokenize_text(text))


def compute_f1(predicted: str, expected: str) -> float:
    """Compute token-level F1 score."""

    predicted_tokens = tokenize_text(predicted)
    expected_tokens = tokenize_text(expected)
    if not predicted_tokens or not expected_tokens:
        return 0.0

    predicted_set = set(predicted_tokens)
    expected_set = set(expected_tokens)
    common_tokens = predicted_set & expected_set
    if not common_tokens:
        return 0.0

    precision = len(common_tokens) / len(predicted_set)
    recall = len(common_tokens) / len(expected_set)
    return 2 * precision * recall / (precision + recall)


def compute_recall_at_k(
    retrieved_source_ids: List[str],
    relevant_source_ids: List[str],
    top_k: int,
) -> float:
    """Compute Recall@K for a sample."""

    if not relevant_source_ids:
        return 1.0

    relevant_set = set(relevant_source_ids)
    retrieved_set = set(retrieved_source_ids[:top_k])
    return len(retrieved_set & relevant_set) / len(relevant_set)


def compute_mrr(retrieved_source_ids: List[str], relevant_source_ids: List[str]) -> float:
    """Compute reciprocal rank of first relevant result."""

    if not relevant_source_ids:
        return 1.0

    relevant_set = set(relevant_source_ids)
    for rank, source_id in enumerate(retrieved_source_ids, start=1):
        if source_id in relevant_set:
            return 1.0 / rank
    return 0.0


def compute_percentile(values: List[float], percentile: float) -> float:
    """Compute percentile using nearest-rank method."""

    if not values:
        return 0.0

    sorted_values = sorted(values)
    index = max(0, math.ceil(len(sorted_values) * percentile) - 1)
    return sorted_values[index]


def aggregate_results(dataset_name: str, case_results: List[EvalCaseResult]) -> EvalSummary:
    """Aggregate sample results into a run summary."""

    total_samples = len(case_results)
    if total_samples == 0:
        raise ValueError("case_results must not be empty")

    step_success_rates = _aggregate_step_success(case_results)
    by_category = _group_metrics(case_results, "category")
    by_difficulty = _group_metrics(case_results, "difficulty")
    failure_buckets = _build_failure_buckets(case_results)
    latencies = [result.latency_ms for result in case_results]
    tool_sample_count = sum(1 for result in case_results if "validation" in result.step_outcomes)
    audited_tool_samples = sum(1 for result in case_results if result.audit_entries > 0)
    answer_f1_values = [result.answer_f1 for result in case_results]

    summary = EvalSummary(
        dataset_name=dataset_name,
        total_samples=total_samples,
        e2e_success_rate=sum(1 for result in case_results if result.success) / total_samples,
        step_success_rates=step_success_rates,
        p95_latency_ms=compute_percentile(latencies, 0.95),
        avg_latency_ms=sum(latencies) / total_samples,
        avg_recall_at_5=sum(result.recall_at_5 for result in case_results) / total_samples,
        avg_recall_at_10=sum(result.recall_at_10 for result in case_results) / total_samples,
        avg_mrr=sum(result.mrr for result in case_results) / total_samples,
        avg_answer_f1=sum(answer_f1_values) / total_samples,
        accuracy=sum(1 for result in case_results if _is_accurate(result)) / total_samples,
        consistency_std=statistics.pstdev(answer_f1_values) if total_samples > 1 else 0.0,
        stability=1.0,
        validation_rejection_rate=_safe_divide(
            sum(1 for result in case_results if result.validation_rejected),
            tool_sample_count,
            0.0,
        ),
        auth_denial_rate=_safe_divide(
            sum(1 for result in case_results if result.auth_denied),
            tool_sample_count,
            0.0,
        ),
        circuit_open_frequency=_safe_divide(
            sum(1 for result in case_results if result.circuit_opened),
            tool_sample_count,
            0.0,
        ),
        audit_completeness=_safe_divide(audited_tool_samples, tool_sample_count, 1.0),
        cost={
            "total_tokens": sum(result.input_tokens + result.output_tokens for result in case_results),
            "tool_calls": sum(result.tool_calls for result in case_results),
            "retrieval_calls": sum(result.retrieval_calls for result in case_results),
        },
        failure_buckets=failure_buckets,
        by_category=by_category,
        by_difficulty=by_difficulty,
        details=case_results,
    )
    return summary


def write_summary_json(summary: EvalSummary, output_path: str) -> None:
    """Write summary to JSON file."""

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as file_handle:
        json.dump(summary.to_dict(), file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _aggregate_step_success(case_results: List[EvalCaseResult]) -> Dict[str, float]:
    """Aggregate success rates per attempted step."""

    success_counts: Dict[str, int] = {}
    attempt_counts: Dict[str, int] = {}
    for case_result in case_results:
        for step_name, succeeded in case_result.step_outcomes.items():
            attempt_counts[step_name] = attempt_counts.get(step_name, 0) + 1
            if succeeded:
                success_counts[step_name] = success_counts.get(step_name, 0) + 1

    return {
        step_name: _safe_divide(success_counts.get(step_name, 0), attempts, 0.0)
        for step_name, attempts in sorted(attempt_counts.items())
    }


def _group_metrics(case_results: List[EvalCaseResult], field_name: str) -> Dict[str, Dict[str, float]]:
    """Aggregate metrics by category-like field."""

    grouped: Dict[str, List[EvalCaseResult]] = {}
    for case_result in case_results:
        group_key = getattr(case_result, field_name)
        grouped.setdefault(group_key, []).append(case_result)

    metrics_by_group: Dict[str, Dict[str, float]] = {}
    for group_key, group_results in grouped.items():
        group_size = len(group_results)
        metrics_by_group[group_key] = {
            "count": float(group_size),
            "e2e_success_rate": sum(1 for item in group_results if item.success) / group_size,
            "avg_answer_f1": sum(item.answer_f1 for item in group_results) / group_size,
            "avg_recall_at_5": sum(item.recall_at_5 for item in group_results) / group_size,
            "avg_mrr": sum(item.mrr for item in group_results) / group_size,
            "avg_latency_ms": sum(item.latency_ms for item in group_results) / group_size,
        }
    return metrics_by_group


def _build_failure_buckets(case_results: List[EvalCaseResult]) -> Dict[str, int]:
    """Build error code histogram for failed cases."""

    buckets: Dict[str, int] = {}
    for case_result in case_results:
        if case_result.success:
            continue
        bucket_name = case_result.error_code or "quality_regression"
        buckets[bucket_name] = buckets.get(bucket_name, 0) + 1
    return buckets


def _is_accurate(case_result: EvalCaseResult) -> bool:
    """Apply accuracy threshold defined in W5 metrics spec."""

    if case_result.success and case_result.error_code is not None and not case_result.expected_answer:
        return True
    if case_result.tool_calls > 0 and case_result.error_code is None:
        return True
    return case_result.answer_f1 >= 0.8


def _safe_divide(numerator: int, denominator: int, default_value: float) -> float:
    """Safely divide two numbers."""

    if denominator == 0:
        return default_value
    return numerator / denominator
