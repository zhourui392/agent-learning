"""
Planning module.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass
class PlanStep:
    """
    One executable unit in an execution plan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    step_id: str
    tool_id: str
    payload: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """
    Ordered execution plan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    request_id: str
    session_id: str
    steps: List[PlanStep]


class PlanningStrategy(ABC):
    """
    Strategy contract for plan generation.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    @abstractmethod
    def build_steps(self, request: Mapping[str, Any]) -> List[PlanStep]:
        """
        Build plan steps for a request.

        @param request: Agent request payload.
        @return: Ordered list of PlanStep.
        """


class KeywordPlanningStrategy(PlanningStrategy):
    """
    Minimal planning strategy based on user intent keywords.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def build_steps(self, request: Mapping[str, Any]) -> List[PlanStep]:
        """
        Build steps with simple deterministic keyword routing.

        @param request: Agent request payload.
        @return: Ordered list of PlanStep.
        """
        user_input = str(request.get("user_input", "")).lower().strip()
        allowed_tools = request.get("allowed_tools", [])

        if "notify" in user_input and "tool.notify" in allowed_tools:
            return [
                PlanStep(
                    step_id="step-1",
                    tool_id="tool.notify",
                    payload={
                        "channel": "slack",
                        "recipient": request.get("metadata", {}).get("recipient", "ops-team"),
                        "message": request.get("user_input", ""),
                    },
                )
            ]

        if "query" in user_input and "tool.query_db" in allowed_tools:
            return [
                PlanStep(
                    step_id="step-1",
                    tool_id="tool.query_db",
                    payload={"sql": "SELECT 1 AS ok", "limit": 10},
                )
            ]

        selected_tool = "tool.search" if "tool.search" in allowed_tools else allowed_tools[0]
        return [
            PlanStep(
                step_id="step-1",
                tool_id=selected_tool,
                payload={"query": request.get("user_input", ""), "top_k": 5},
            )
        ]


class Planner:
    """
    Orchestrates strategy and builds an execution plan object.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, strategy: PlanningStrategy | None = None) -> None:
        """
        Initialize planner.

        @param strategy: Optional planning strategy.
        @return: None.
        """
        self._strategy = strategy or KeywordPlanningStrategy()

    def create_plan(self, request: Mapping[str, Any]) -> ExecutionPlan:
        """
        Create executable plan from request.

        @param request: Validated request payload.
        @return: ExecutionPlan instance.
        """
        self._validate_request(request)
        steps = self._strategy.build_steps(request)
        if not steps:
            raise ValueError("planner produced empty plan")

        return ExecutionPlan(
            request_id=request["request_id"],
            session_id=request["session_id"],
            steps=steps,
        )

    def _validate_request(self, request: Mapping[str, Any]) -> None:
        """
        Guard required planning fields.

        @param request: Request payload.
        @return: None.
        """
        required_fields = ("request_id", "session_id", "user_input", "allowed_tools")
        for required_field in required_fields:
            if required_field not in request:
                raise ValueError(f"missing required planning field: {required_field}")
        if not request["allowed_tools"]:
            raise ValueError("allowed_tools must not be empty")
