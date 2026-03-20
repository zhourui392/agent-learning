"""Weekly report generator -- reads regression results from ConfigCenter."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from src.ops_report.models import TrendPoint, WeeklyReportData
from src.ops_report.trend_analyzer import TrendAnalyzer

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


class WeeklyReportGenerator:
    """Generate a weekly ops report from ConfigCenter regression history.

    Reads from namespace ``"regression_results"``.
    """

    def __init__(
        self,
        config_center: "ConfigCenter",
        namespace: str = "regression_results",
    ) -> None:
        self._cc = config_center
        self._namespace = namespace
        self._analyzer = TrendAnalyzer()

    def collect_points(self) -> List[TrendPoint]:
        """Read all regression result entries and convert to TrendPoints."""
        entries = self._cc.list_namespace(self._namespace)
        points: List[TrendPoint] = []
        for entry in entries:
            v = entry.value
            if not isinstance(v, dict):
                continue
            points.append(TrendPoint(
                run_id=v.get("run_id", entry.key),
                metrics={
                    "overall_score": float(v.get("overall_score", 0.0)),
                    "technical_score": float(v.get("technical_score", 0.0)),
                    "business_score": float(v.get("business_score", 0.0)),
                },
                gate_passed=bool(v.get("gate_passed", False)),
                timestamp=float(v.get("timestamp", 0.0)),
            ))
        points.sort(key=lambda p: p.timestamp)
        return points

    def generate(
        self,
        period_start: str,
        period_end: str,
    ) -> WeeklyReportData:
        """Generate the weekly report data."""
        points = self.collect_points()
        trend = self._analyzer.analyze(points)

        total = len(points)
        pass_count = sum(1 for p in points if p.gate_passed)
        avg_score = (
            sum(p.metrics.get("overall_score", 0.0) for p in points) / total
            if total > 0
            else 0.0
        )

        return WeeklyReportData(
            period_start=period_start,
            period_end=period_end,
            total_runs=total,
            gate_pass_rate=pass_count / total if total > 0 else 0.0,
            avg_overall_score=round(avg_score, 4),
            trend=trend,
            points=points,
        )

    def render_markdown(
        self,
        period_start: str,
        period_end: str,
    ) -> str:
        """Generate the report and render as Markdown."""
        data = self.generate(period_start, period_end)
        lines = [
            f"# Weekly Ops Report ({data.period_start} ~ {data.period_end})",
            "",
            "## Summary",
            "",
            f"- Total regression runs: **{data.total_runs}**",
            f"- Gate pass rate: **{data.gate_pass_rate:.1%}**",
            f"- Average overall score: **{data.avg_overall_score:.4f}**",
            f"- Overall trend: **{data.trend.overall_trend}**",
            "",
        ]

        if data.trend.regressions:
            lines.append("## Regressions")
            lines.append("")
            for r in data.trend.regressions:
                lines.append(f"- {r}")
            lines.append("")

        if data.trend.improvements:
            lines.append("## Improvements")
            lines.append("")
            for i in data.trend.improvements:
                lines.append(f"- {i}")
            lines.append("")

        if data.points:
            lines.append("## Run Details")
            lines.append("")
            lines.append("| Run ID | Overall Score | Gate Passed |")
            lines.append("|--------|---------------|-------------|")
            for p in data.points:
                score = p.metrics.get("overall_score", 0.0)
                passed = "Yes" if p.gate_passed else "No"
                lines.append(f"| {p.run_id} | {score:.4f} | {passed} |")
            lines.append("")

        return "\n".join(lines)
