"""Incident drill report generation helpers for W6."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from src.observability.alert_manager import AlertEvent
from src.observability.latency_analyzer import LatencyHotspot


class IncidentDrillReporter:
    """Render one lightweight incident drill report from current artifacts."""

    def write_report(
        self,
        output_path: str,
        dataset_name: str,
        firing_alerts: Iterable[AlertEvent],
        latency_hotspots: List[LatencyHotspot],
    ) -> None:
        """Write a Markdown incident drill report."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        alert_lines = [
            f"- `{event.name}` {event.severity}: {event.description}"
            for event in firing_alerts
        ] or ["- No active alerts"]
        hotspot_lines = [
            f"- `{hotspot.component}.{hotspot.span_name}` avg={hotspot.avg_duration_ms:.2f}ms p95={hotspot.p95_duration_ms:.2f}ms"
            for hotspot in latency_hotspots
        ] or ["- No latency hotspots"]
        lines = [
            "# W6 Incident Drill",
            "",
            f"- Dataset: `{dataset_name}`",
            "- Trigger: automated drill from latest observability artifacts",
            "",
            "## Active Alerts",
            "",
            *alert_lines,
            "",
            "## Latency Hotspots",
            "",
            *hotspot_lines,
            "",
            "## Suggested Actions",
            "",
            "- Check dashboard snapshot for current blast radius.",
            "- Follow on-call escalation runbook for firing alerts.",
            "- Replay failed cases when failure buckets are non-empty.",
        ]
        output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
