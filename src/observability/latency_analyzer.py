"""Latency hotspot analysis helpers for W6."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from eval.scorer import EvalCaseResult
from src.observability.tracer import SpanRecord


@dataclass
class LatencyHotspot:
    """One latency hotspot row."""

    component: str
    span_name: str
    avg_duration_ms: float
    p95_duration_ms: float
    sample_count: int


class LatencyAnalyzer:
    """Analyze spans and case results for slow-path hotspots."""

    def build_hotspots(self, spans: Iterable[SpanRecord], limit: int = 5) -> List[LatencyHotspot]:
        """Group spans by component and name, then rank by P95."""

        grouped: Dict[tuple, List[float]] = {}
        for span_record in spans:
            key = (span_record.component, span_record.name)
            grouped.setdefault(key, []).append(span_record.duration_ms)

        hotspots: List[LatencyHotspot] = []
        for (component, span_name), durations in grouped.items():
            hotspots.append(
                LatencyHotspot(
                    component=component,
                    span_name=span_name,
                    avg_duration_ms=sum(durations) / len(durations),
                    p95_duration_ms=self._percentile(durations, 0.95),
                    sample_count=len(durations),
                )
            )
        hotspots.sort(key=lambda item: (-item.p95_duration_ms, -item.avg_duration_ms, item.component))
        return hotspots[:limit]

    def write_markdown_report(
        self,
        case_results: Iterable[EvalCaseResult],
        spans: Iterable[SpanRecord],
        output_path: str,
        limit: int = 5,
    ) -> None:
        """Persist latency breakdown report as Markdown."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        case_latencies = [case_result.latency_ms for case_result in case_results]
        lines = [
            "# Latency Breakdown",
            "",
            f"- Samples: {len(case_latencies)}",
            f"- Avg Case Latency: {self._average(case_latencies):.2f} ms",
            f"- P95 Case Latency: {self._percentile(case_latencies, 0.95):.2f} ms",
            "",
            "| Component | Span | Avg Duration (ms) | P95 Duration (ms) | Samples |",
            "|-----------|------|-------------------|-------------------|---------|",
        ]
        hotspots = self.build_hotspots(spans, limit)
        for hotspot in hotspots:
            lines.append(
                f"| {hotspot.component} | {hotspot.span_name} | {hotspot.avg_duration_ms:.2f} | {hotspot.p95_duration_ms:.2f} | {hotspot.sample_count} |"
            )
        if not hotspots:
            lines.append("| none | none | 0.00 | 0.00 | 0 |")
        output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _average(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _percentile(self, values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = max(0, int(len(sorted_values) * percentile + 0.999999) - 1)
        return sorted_values[index]
