"""Error categorization and TopN report helpers for W6."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from eval.scorer import EvalCaseResult


@dataclass
class ErrorBucketEntry:
    """One aggregated error bucket row."""

    category: str
    error_code: str
    priority: int
    count: int
    sample_ids: List[str]


class ErrorBucketAnalyzer:
    """Aggregate failed samples into prioritized buckets."""

    def build_topn(
        self,
        case_results: Iterable[EvalCaseResult],
        limit: int = 5,
    ) -> List[ErrorBucketEntry]:
        """Build prioritized TopN buckets from case results."""

        grouped: Dict[tuple, ErrorBucketEntry] = {}
        for case_result in case_results:
            if case_result.success:
                continue
            error_code = case_result.error_code or "quality_regression"
            category = self._classify_category(error_code)
            priority = self._priority_of(error_code)
            group_key = (category, error_code)
            if group_key not in grouped:
                grouped[group_key] = ErrorBucketEntry(category, error_code, priority, 0, [])
            entry = grouped[group_key]
            entry.count += 1
            entry.sample_ids.append(case_result.sample_id)

        entries = sorted(
            grouped.values(),
            key=lambda item: (item.priority, -item.count, item.error_code),
        )
        return entries[:limit]

    def write_markdown_report(
        self,
        case_results: Iterable[EvalCaseResult],
        output_path: str,
        limit: int = 5,
    ) -> None:
        """Persist TopN error report as Markdown."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Error TopN",
            "",
            "| Category | Error Code | Priority | Count | Sample IDs |",
            "|----------|------------|----------|-------|------------|",
        ]
        for entry in self.build_topn(case_results, limit):
            sample_ids = ", ".join(entry.sample_ids)
            lines.append(
                f"| {entry.category} | {entry.error_code} | P{entry.priority} | {entry.count} | {sample_ids} |"
            )
        if len(lines) == 4:
            lines.append("| none | none | P0 | 0 | - |")
        output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _classify_category(self, error_code: str) -> str:
        mapping = {
            "missing_required_field": "data",
            "invalid_tool_name": "tool",
            "tool_execution_failed": "tool",
            "circuit_open": "system",
            "rate_limited": "system",
            "unauthorized": "strategy",
            "quality_regression": "model",
        }
        return mapping.get(error_code, "system")

    def _priority_of(self, error_code: str) -> int:
        priorities = {
            "circuit_open": 1,
            "tool_execution_failed": 1,
            "rate_limited": 2,
            "unauthorized": 3,
            "missing_required_field": 3,
            "invalid_tool_name": 2,
            "quality_regression": 2,
        }
        return priorities.get(error_code, 3)
