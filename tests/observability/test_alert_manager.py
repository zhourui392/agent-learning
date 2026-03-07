"""Unit tests for W6 alert manager and dashboard exporter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.observability.alert_manager import AlertManager
from src.observability.dashboard_exporter import DashboardExporter
from src.observability.incident_drill import IncidentDrillReporter
from src.observability.latency_analyzer import LatencyHotspot


class AlertManagerTestCase(unittest.TestCase):
    """Verify alert evaluation and snapshot generation."""

    def test_alert_manager_detects_firing_rules(self) -> None:
        """Low success rate and high token cost should fire alerts."""

        manager = AlertManager()
        summary = {
            "dataset_name": "smoke.jsonl",
            "e2e_success_rate": 0.6,
            "p95_latency_ms": 8.0,
            "accuracy": 0.5,
            "avg_answer_f1": 0.5,
            "failure_buckets": {"tool_execution_failed": 1},
            "cost": {"total_tokens": 300},
            "by_category": {},
            "by_difficulty": {},
        }

        events = manager.evaluate(summary)
        firing_names = {event.name for event in events if event.status == "firing"}

        self.assertIn("low_e2e_success_rate", firing_names)
        self.assertIn("high_p95_latency", firing_names)
        self.assertIn("token_cost_spike", firing_names)

    def test_dashboard_and_incident_reports_write_outputs(self) -> None:
        """Dashboard snapshot and incident report should be written."""

        manager = AlertManager()
        exporter = DashboardExporter()
        reporter = IncidentDrillReporter()
        summary = {
            "dataset_name": "smoke.jsonl",
            "e2e_success_rate": 0.8,
            "accuracy": 0.6,
            "avg_answer_f1": 0.7,
            "avg_latency_ms": 1.0,
            "p95_latency_ms": 2.0,
            "failure_buckets": {"quality_regression": 1},
            "cost": {"total_tokens": 183},
            "by_category": {},
            "by_difficulty": {},
        }
        events = manager.evaluate(summary)
        payload = [event.to_dict() for event in events]
        snapshot = exporter.build_snapshot(summary, payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "dashboard-snapshot.json"
            report_path = Path(temp_dir) / "incident-drill.md"
            exporter.write_snapshot(snapshot, str(snapshot_path))
            reporter.write_report(
                str(report_path),
                "smoke.jsonl",
                [event for event in events if event.status == "firing"],
                [LatencyHotspot("retrieval", "retrieve", 10.0, 20.0, 3)],
            )

            self.assertTrue(snapshot_path.exists())
            self.assertTrue(report_path.exists())
            self.assertIn("firing_count", snapshot_path.read_text(encoding="utf-8"))
            self.assertIn("# W6 Incident Drill", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
