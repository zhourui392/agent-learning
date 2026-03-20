"""Tests for WeeklyReportGenerator."""

import unittest

from src.config_center.config_store import ConfigCenter
from src.ops_report.weekly_report_generator import WeeklyReportGenerator


class TestWeeklyReportGenerator(unittest.TestCase):
    def setUp(self):
        self.cc = ConfigCenter()
        self.generator = WeeklyReportGenerator(self.cc)

    def test_empty_report(self):
        report = self.generator.generate("2026-03-10", "2026-03-17")
        self.assertEqual(report.total_runs, 0)
        self.assertEqual(report.gate_pass_rate, 0.0)

    def test_report_with_data(self):
        for i in range(3):
            self.cc.put("regression_results", f"run-{i}", {
                "run_id": f"run-{i}",
                "gate_passed": i < 2,
                "overall_score": 0.7 + i * 0.05,
                "technical_score": 0.8,
                "business_score": 0.6,
                "timestamp": 1000.0 + i,
            })
        report = self.generator.generate("2026-03-10", "2026-03-17")
        self.assertEqual(report.total_runs, 3)
        self.assertAlmostEqual(report.gate_pass_rate, 2 / 3, places=2)

    def test_render_markdown(self):
        self.cc.put("regression_results", "run-1", {
            "run_id": "run-1",
            "gate_passed": True,
            "overall_score": 0.85,
            "technical_score": 0.9,
            "business_score": 0.7,
            "timestamp": 1000.0,
        })
        md = self.generator.render_markdown("2026-03-10", "2026-03-17")
        self.assertIn("Weekly Ops Report", md)
        self.assertIn("run-1", md)
        self.assertIn("0.85", md)

    def test_collect_points_sorted_by_timestamp(self):
        self.cc.put("regression_results", "late", {
            "run_id": "late", "gate_passed": True,
            "overall_score": 0.8, "timestamp": 2000.0,
            "technical_score": 0.8, "business_score": 0.7,
        })
        self.cc.put("regression_results", "early", {
            "run_id": "early", "gate_passed": True,
            "overall_score": 0.7, "timestamp": 1000.0,
            "technical_score": 0.7, "business_score": 0.6,
        })
        points = self.generator.collect_points()
        self.assertEqual(points[0].run_id, "early")
        self.assertEqual(points[1].run_id, "late")


if __name__ == "__main__":
    unittest.main()
