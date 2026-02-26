"""
Planning module.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Set


@dataclass
class GraphLimits:
    """
    Graph constraints for one plan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    max_depth: int = 6
    max_parallel: int = 4


@dataclass
class PlanStep:
    """
    One executable unit in an execution plan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    step_id: str
    goal: str
    tool_id: str
    payload: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    done_criteria: str = "tool result success is true"
    timeout_seconds: int = 8
    allow_rollback: bool = True


@dataclass
class ExecutionPlan:
    """
    Ordered execution plan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    request_id: str
    session_id: str
    trace_id: str
    plan_version: int
    steps: List[PlanStep]
    risk_flags: List[str] = field(default_factory=list)
    graph_limits: GraphLimits = field(default_factory=GraphLimits)


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
        Build steps with deterministic keyword routing.

        @param request: Agent request payload.
        @return: Ordered list of PlanStep.
        """
        user_input = str(request.get("user_input", "")).strip()
        user_input_lower = user_input.lower()
        allowed_tools = list(request.get("allowed_tools", []))

        if "notify" in user_input_lower and "tool.notify" in allowed_tools:
            return [
                PlanStep(
                    step_id="step-1",
                    goal="send notification",
                    tool_id="tool.notify",
                    payload={
                        "channel": "slack",
                        "recipient": request.get("metadata", {}).get("recipient", "ops-team"),
                        "message": user_input,
                    },
                    done_criteria="notification status is queued",
                )
            ]

        can_search = "tool.search" in allowed_tools
        can_query = "tool.query_db" in allowed_tools
        if ("analyze" in user_input_lower or "analysis" in user_input_lower) and can_search and can_query:
            return [
                PlanStep(
                    step_id="step-1",
                    goal="collect external context",
                    tool_id="tool.search",
                    payload={"query": user_input, "top_k": 5},
                    done_criteria="search returns at least one item",
                ),
                PlanStep(
                    step_id="step-2",
                    goal="collect structured metrics",
                    tool_id="tool.query_db",
                    payload={"sql": "SELECT 1 AS ok", "limit": 10},
                    done_criteria="query returns at least one row",
                ),
                PlanStep(
                    step_id="step-3",
                    goal="final consistency check",
                    tool_id="tool.search",
                    payload={"query": f"summary check: {user_input}", "top_k": 3},
                    depends_on=["step-1", "step-2"],
                    done_criteria="summary check result is available",
                ),
            ]

        if "query" in user_input_lower and can_query:
            return [
                PlanStep(
                    step_id="step-1",
                    goal="run query",
                    tool_id="tool.query_db",
                    payload={"sql": "SELECT 1 AS ok", "limit": 10},
                    done_criteria="query returns row_count >= 1",
                )
            ]

        selected_tool = "tool.search" if can_search else allowed_tools[0]
        return [
            PlanStep(
                step_id="step-1",
                goal="search relevant information",
                tool_id=selected_tool,
                payload={"query": user_input, "top_k": 5},
                done_criteria="search result is not empty",
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

        metadata = request.get("metadata", {})
        default_step_timeout = metadata.get("step_timeout_seconds")
        if default_step_timeout is not None:
            timeout_seconds = int(default_step_timeout)
            for step in steps:
                step.timeout_seconds = timeout_seconds

        graph_limits = GraphLimits(
            max_depth=int(metadata.get("max_depth", 6)),
            max_parallel=int(metadata.get("max_parallel", 4)),
        )
        plan_version = int(metadata.get("plan_version", 1))
        if plan_version < 1:
            raise ValueError("plan_version must be >= 1")

        trace_id = str(metadata.get("trace_id") or f"trace-{request['request_id']}-v{plan_version}")
        plan = ExecutionPlan(
            request_id=request["request_id"],
            session_id=request["session_id"],
            trace_id=trace_id,
            plan_version=plan_version,
            steps=steps,
            risk_flags=self._infer_risks(request=request, steps=steps),
            graph_limits=graph_limits,
        )
        self.validate_plan(plan=plan, allowed_tools=request["allowed_tools"])
        return plan

    def validate_plan(self, plan: ExecutionPlan, allowed_tools: List[str]) -> None:
        """
        Validate structural rules and quality checks for plan.

        @param plan: Plan to be validated.
        @param allowed_tools: Request-level allowed tools.
        @return: None.
        """
        if plan.graph_limits.max_depth < 1:
            raise ValueError("graph max_depth must be >= 1")
        if plan.graph_limits.max_parallel < 1:
            raise ValueError("graph max_parallel must be >= 1")

        self._validate_step_fields(plan=plan, allowed_tools=allowed_tools)
        self._validate_dependencies(plan)
        self._validate_acyclic(plan)
        self._validate_depth(plan)
        self._validate_parallelism(plan)

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

    def _validate_step_fields(self, plan: ExecutionPlan, allowed_tools: List[str]) -> None:
        """
        Validate step-level executability and observability fields.

        @param plan: Plan object.
        @param allowed_tools: Request-level allowed tool IDs.
        @return: None.
        """
        step_ids: Set[str] = set()
        allowed_set = set(allowed_tools)
        for step in plan.steps:
            if not step.step_id:
                raise ValueError("step_id must not be empty")
            if step.step_id in step_ids:
                raise ValueError(f"duplicate step_id: {step.step_id}")
            step_ids.add(step.step_id)

            if not step.goal:
                raise ValueError(f"step {step.step_id} missing goal")
            if not step.done_criteria:
                raise ValueError(f"step {step.step_id} missing done_criteria")
            if not step.tool_id:
                raise ValueError(f"step {step.step_id} missing tool_id")
            if step.tool_id not in allowed_set:
                raise ValueError(f"step {step.step_id} uses disallowed tool: {step.tool_id}")
            if not isinstance(step.payload, dict):
                raise ValueError(f"step {step.step_id} payload must be object")
            if step.timeout_seconds < 1:
                raise ValueError(f"step {step.step_id} timeout_seconds must be >= 1")

    def _validate_dependencies(self, plan: ExecutionPlan) -> None:
        """
        Validate dependency references.

        @param plan: Plan object.
        @return: None.
        """
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            for dependency_step_id in step.depends_on:
                if dependency_step_id not in step_ids:
                    raise ValueError(
                        f"step {step.step_id} depends on unknown step: {dependency_step_id}"
                    )

    def _validate_acyclic(self, plan: ExecutionPlan) -> None:
        """
        Validate that dependency graph is acyclic.

        @param plan: Plan object.
        @return: None.
        """
        dependency_map = {step.step_id: list(step.depends_on) for step in plan.steps}
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def dfs(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise ValueError(f"cycle detected at step: {step_id}")
            visiting.add(step_id)
            for dependency_step_id in dependency_map.get(step_id, []):
                dfs(dependency_step_id)
            visiting.remove(step_id)
            visited.add(step_id)

        for step in plan.steps:
            dfs(step.step_id)

    def _validate_depth(self, plan: ExecutionPlan) -> None:
        """
        Validate graph depth does not exceed configured limit.

        @param plan: Plan object.
        @return: None.
        """
        depth_map = self._build_depth_map(plan)
        max_depth = max(depth_map.values())
        if max_depth > plan.graph_limits.max_depth:
            raise ValueError(
                f"plan depth {max_depth} exceeds max_depth {plan.graph_limits.max_depth}"
            )

    def _validate_parallelism(self, plan: ExecutionPlan) -> None:
        """
        Validate estimated parallelism does not exceed configured limit.

        @param plan: Plan object.
        @return: None.
        """
        depth_map = self._build_depth_map(plan)
        depth_count: Dict[int, int] = {}
        for depth in depth_map.values():
            depth_count[depth] = depth_count.get(depth, 0) + 1
        estimated_parallel = max(depth_count.values()) if depth_count else 0
        if estimated_parallel > plan.graph_limits.max_parallel:
            raise ValueError(
                "plan estimated parallelism "
                f"{estimated_parallel} exceeds max_parallel {plan.graph_limits.max_parallel}"
            )

    def _build_depth_map(self, plan: ExecutionPlan) -> Dict[str, int]:
        """
        Build per-step depth map from dependency graph.

        @param plan: Plan object.
        @return: Mapping from step_id to depth.
        """
        dependency_map = {step.step_id: list(step.depends_on) for step in plan.steps}
        cache: Dict[str, int] = {}

        def depth_of(step_id: str) -> int:
            if step_id in cache:
                return cache[step_id]
            dependencies = dependency_map.get(step_id, [])
            if not dependencies:
                cache[step_id] = 1
                return 1
            depth = 1 + max(depth_of(dependency_step_id) for dependency_step_id in dependencies)
            cache[step_id] = depth
            return depth

        for step in plan.steps:
            depth_of(step.step_id)
        return cache

    def _infer_risks(self, request: Mapping[str, Any], steps: List[PlanStep]) -> List[str]:
        """
        Infer risk flags from request and generated plan.

        @param request: Original request payload.
        @param steps: Planned steps.
        @return: Sorted risk flags.
        """
        risk_flags: Set[str] = set()
        step_tool_ids = {step.tool_id for step in steps}
        if "tool.notify" in step_tool_ids:
            risk_flags.add("high_cost")
        if "tool.search" in step_tool_ids or "tool.query_db" in step_tool_ids:
            risk_flags.add("external_dependency")

        user_input = str(request.get("user_input", "")).lower()
        uncertain_keywords = ("maybe", "unknown", "uncertain", "guess")
        if any(keyword in user_input for keyword in uncertain_keywords):
            risk_flags.add("uncertain_information")

        if request.get("metadata", {}).get("high_cost"):
            risk_flags.add("high_cost")

        return sorted(risk_flags)
