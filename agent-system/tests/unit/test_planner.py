"""
Unit tests for planner module.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import unittest
from typing import Any, List, Mapping

from src.agent.planner import PlanStep, Planner, PlanningStrategy


class CycleStrategy(PlanningStrategy):
    """
    Test strategy that generates cyclic dependency graph.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def build_steps(self, request: Mapping[str, Any]) -> List[PlanStep]:
        """
        Build two steps with mutual dependency.

        @param request: Agent request payload.
        @return: List of cyclic steps.
        """
        return [
            PlanStep(
                step_id="step-1",
                goal="cycle a",
                tool_id="tool.search",
                payload={"query": "a"},
                depends_on=["step-2"],
                done_criteria="done",
            ),
            PlanStep(
                step_id="step-2",
                goal="cycle b",
                tool_id="tool.search",
                payload={"query": "b"},
                depends_on=["step-1"],
                done_criteria="done",
            ),
        ]


class PlannerUnitTestCase(unittest.TestCase):
    """
    Verify planner graph and metadata behavior.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def test_create_plan_contains_trace_version_and_risks(self) -> None:
        """
        Planner should produce trace_id, version, and risk flags.

        @param self: Test instance.
        @return: None.
        """
        planner = Planner()
        request = {
            "request_id": "req-plan-1",
            "session_id": "sess-plan-1",
            "user_input": "analyze unknown issue",
            "allowed_tools": ["tool.search", "tool.query_db"],
            "metadata": {
                "trace_id": "trace-custom-1",
                "plan_version": 2,
                "max_depth": 6,
                "max_parallel": 4,
            },
        }

        plan = planner.create_plan(request)

        self.assertEqual(plan.trace_id, "trace-custom-1")
        self.assertEqual(plan.plan_version, 2)
        self.assertIn("external_dependency", plan.risk_flags)
        self.assertIn("uncertain_information", plan.risk_flags)
        self.assertGreaterEqual(len(plan.steps), 3)

    def test_cycle_plan_should_fail_validation(self) -> None:
        """
        Planner should reject cyclic dependency graph.

        @param self: Test instance.
        @return: None.
        """
        planner = Planner(strategy=CycleStrategy())
        request = {
            "request_id": "req-plan-cycle",
            "session_id": "sess-plan-cycle",
            "user_input": "cycle test",
            "allowed_tools": ["tool.search"],
        }

        with self.assertRaises(ValueError):
            planner.create_plan(request)

    def test_plan_parallelism_exceeding_limit_should_fail(self) -> None:
        """
        Planner should reject plan when estimated parallelism exceeds max_parallel.

        @param self: Test instance.
        @return: None.
        """
        planner = Planner()
        request = {
            "request_id": "req-plan-parallel",
            "session_id": "sess-plan-parallel",
            "user_input": "analyze service quality",
            "allowed_tools": ["tool.search", "tool.query_db"],
            "metadata": {
                "max_parallel": 1,
            },
        }

        with self.assertRaises(ValueError):
            planner.create_plan(request)


if __name__ == "__main__":
    unittest.main()
