"""Dashboard snapshot exporter for W6."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class DashboardExporter:
    """Build one portable dashboard snapshot from summary and alerts."""

    def build_snapshot(
        self,
        summary: Dict[str, Any],
        alert_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a dashboard-friendly snapshot."""

        firing_alerts = [event for event in alert_events if event.get("status") == "firing"]
        return {
            "dataset_name": summary.get("dataset_name"),
            "summary": {
                "e2e_success_rate": summary.get("e2e_success_rate", 0.0),
                "accuracy": summary.get("accuracy", 0.0),
                "avg_answer_f1": summary.get("avg_answer_f1", 0.0),
                "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
                "p95_latency_ms": summary.get("p95_latency_ms", 0.0),
                "total_tokens": summary.get("cost", {}).get("total_tokens", 0),
            },
            "breakdowns": {
                "failure_buckets": summary.get("failure_buckets", {}),
                "by_category": summary.get("by_category", {}),
                "by_difficulty": summary.get("by_difficulty", {}),
            },
            "alerts": {
                "firing_count": len(firing_alerts),
                "firing": firing_alerts,
            },
        }

    def write_snapshot(self, snapshot: Dict[str, Any], output_path: str) -> None:
        """Persist dashboard snapshot as JSON."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as file_handle:
            json.dump(snapshot, file_handle, ensure_ascii=False, indent=2)
            file_handle.write("\n")
