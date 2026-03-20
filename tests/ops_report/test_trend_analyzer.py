"""Tests for TrendAnalyzer."""

import unittest

from src.ops_report.models import TrendPoint
from src.ops_report.trend_analyzer import TrendAnalyzer


class TestTrendAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TrendAnalyzer()

    def test_empty_points(self):
        result = self.analyzer.analyze([])
        self.assertEqual(result.overall_trend, "stable")

    def test_single_point(self):
        result = self.analyzer.analyze([
            TrendPoint(run_id="r1", metrics={"overall_score": 0.8}),
        ])
        self.assertEqual(result.overall_trend, "stable")

    def test_improving_trend(self):
        points = [
            TrendPoint(run_id="r1", metrics={"overall_score": 0.5}),
            TrendPoint(run_id="r2", metrics={"overall_score": 0.6}),
            TrendPoint(run_id="r3", metrics={"overall_score": 0.7}),
        ]
        result = self.analyzer.analyze(points)
        self.assertEqual(result.overall_trend, "improving")

    def test_degrading_trend(self):
        points = [
            TrendPoint(run_id="r1", metrics={"overall_score": 0.9}),
            TrendPoint(run_id="r2", metrics={"overall_score": 0.8}),
            TrendPoint(run_id="r3", metrics={"overall_score": 0.7}),
        ]
        result = self.analyzer.analyze(points)
        self.assertEqual(result.overall_trend, "degrading")

    def test_stable_trend(self):
        points = [
            TrendPoint(run_id="r1", metrics={"overall_score": 0.8}),
            TrendPoint(run_id="r2", metrics={"overall_score": 0.8}),
            TrendPoint(run_id="r3", metrics={"overall_score": 0.81}),
        ]
        result = self.analyzer.analyze(points)
        self.assertEqual(result.overall_trend, "stable")

    def test_regression_detection(self):
        points = [
            TrendPoint(run_id="r1", metrics={"latency": 100.0}),
            TrendPoint(run_id="r2", metrics={"latency": 90.0}),
            TrendPoint(run_id="r3", metrics={"latency": 80.0}),
        ]
        result = self.analyzer.analyze(points)
        self.assertIn("latency", result.regressions)


if __name__ == "__main__":
    unittest.main()
