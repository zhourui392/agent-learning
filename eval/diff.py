"""W5 baseline diff tool."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class DiffThresholds:
    """Gate thresholds for W5 baseline comparison."""

    min_e2e_success_rate_delta: float = -0.05
    min_answer_f1_delta: float = -0.05
    min_accuracy_delta: float = -0.05
    max_p95_latency_ratio: float = 1.2
    max_total_tokens_ratio: float = 1.2


@dataclass
class DiffIssue:
    """One baseline regression issue."""

    metric: str
    baseline: float
    current: float
    message: str


@dataclass
class DiffResult:
    """Diff outcome for one evaluation run."""

    passed: bool
    issues: List[DiffIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""

        return {
            "passed": self.passed,
            "issues": [
                {
                    "metric": issue.metric,
                    "baseline": issue.baseline,
                    "current": issue.current,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


def compare_reports(
    baseline: Dict[str, Any],
    current: Dict[str, Any],
    thresholds: DiffThresholds,
) -> DiffResult:
    """Compare current report to baseline and return gating decision."""

    issues: List[DiffIssue] = []
    _check_delta(
        issues,
        metric="e2e_success_rate",
        baseline=float(baseline.get("e2e_success_rate", 0.0)),
        current=float(current.get("e2e_success_rate", 0.0)),
        min_delta=thresholds.min_e2e_success_rate_delta,
    )
    _check_delta(
        issues,
        metric="avg_answer_f1",
        baseline=float(baseline.get("avg_answer_f1", 0.0)),
        current=float(current.get("avg_answer_f1", 0.0)),
        min_delta=thresholds.min_answer_f1_delta,
    )
    _check_delta(
        issues,
        metric="accuracy",
        baseline=float(baseline.get("accuracy", 0.0)),
        current=float(current.get("accuracy", 0.0)),
        min_delta=thresholds.min_accuracy_delta,
    )
    _check_ratio(
        issues,
        metric="p95_latency_ms",
        baseline=float(baseline.get("p95_latency_ms", 0.0)),
        current=float(current.get("p95_latency_ms", 0.0)),
        max_ratio=thresholds.max_p95_latency_ratio,
    )
    _check_ratio(
        issues,
        metric="cost.total_tokens",
        baseline=float(baseline.get("cost", {}).get("total_tokens", 0.0)),
        current=float(current.get("cost", {}).get("total_tokens", 0.0)),
        max_ratio=thresholds.max_total_tokens_ratio,
    )
    return DiffResult(passed=len(issues) == 0, issues=issues)


def load_report(report_path: str) -> Dict[str, Any]:
    """Load evaluation summary JSON."""

    with Path(report_path).open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def write_diff_report(diff_result: DiffResult, output_path: str) -> None:
    """Write Markdown diff report."""

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# W5 Baseline Diff Report",
        "",
        f"- Gate: {'PASS' if diff_result.passed else 'FAIL'}",
        "",
        "## Issues",
        "",
    ]
    if not diff_result.issues:
        lines.append("- No regressions detected")
    else:
        for issue in diff_result.issues:
            lines.append(
                f"- `{issue.metric}` baseline={issue.baseline:.4f}, current={issue.current:.4f}: {issue.message}"
            )
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _check_delta(
    issues: List[DiffIssue],
    metric: str,
    baseline: float,
    current: float,
    min_delta: float,
) -> None:
    """Append issue when current metric regresses beyond delta threshold."""

    delta = current - baseline
    if delta < min_delta:
        issues.append(
            DiffIssue(
                metric=metric,
                baseline=baseline,
                current=current,
                message=f"delta {delta:.4f} is below threshold {min_delta:.4f}",
            )
        )


def _check_ratio(
    issues: List[DiffIssue],
    metric: str,
    baseline: float,
    current: float,
    max_ratio: float,
) -> None:
    """Append issue when current metric exceeds ratio threshold."""

    if baseline <= 0:
        return
    ratio = current / baseline
    if ratio > max_ratio:
        issues.append(
            DiffIssue(
                metric=metric,
                baseline=baseline,
                current=current,
                message=f"ratio {ratio:.4f} exceeds threshold {max_ratio:.4f}",
            )
        )


def main() -> None:
    """CLI entry for baseline diff."""

    parser = argparse.ArgumentParser(description="Compare W5 eval summary against baseline")
    parser.add_argument("--baseline", required=True, help="Path to baseline summary JSON")
    parser.add_argument("--current", required=True, help="Path to current summary JSON")
    parser.add_argument("--output", default="eval/results/diff-report.md", help="Output Markdown path")
    args = parser.parse_args()

    baseline_report = load_report(args.baseline)
    current_report = load_report(args.current)
    diff_result = compare_reports(baseline_report, current_report, DiffThresholds())
    write_diff_report(diff_result, args.output)
    print(json.dumps(diff_result.to_dict(), ensure_ascii=False, indent=2))
    if not diff_result.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
