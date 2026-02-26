"""
Replanning module.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List

from src.agent.planner import ExecutionPlan, PlanStep


@dataclass
class ReplanDecision:
    """
    Decision produced by replan policy.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    should_replan: bool
    strategy: str
    reason: str
    message: str
    requires_human_handoff: bool = False


@dataclass
class StepIdMapping:
    """
    Mapping between old and new step IDs after replan.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    source_step_id: str
    target_step_id: str
    plan_version: int


@dataclass
class ReplanOutcome:
    """
    Replan output with new plan and mapping details.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    plan: ExecutionPlan
    decision: ReplanDecision
    step_id_mappings: List[StepIdMapping] = field(default_factory=list)


class Replanner:
    """
    Replanner for failed steps and dependency issues.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def replan_after_failure(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep,
        error: Dict[str, Any],
    ) -> ReplanOutcome:
        """
        Build replan outcome after one step failure.

        @param plan: Current execution plan.
        @param failed_step: Failed plan step.
        @param error: Step error payload.
        @return: ReplanOutcome.
        """
        decision = self._build_decision(error=error, reason="step_failed")
        if not decision.should_replan:
            return ReplanOutcome(plan=plan, decision=decision)

        if decision.strategy == "local_replace":
            return self._local_replace(plan=plan, failed_step=failed_step, decision=decision)

        return self._rollback_retry(plan=plan, failed_step=failed_step, decision=decision)

    def replan_for_missing_dependency(self, plan: ExecutionPlan, blocked_step_id: str) -> ReplanOutcome:
        """
        Build replan outcome when dependency graph cannot make progress.

        @param plan: Current execution plan.
        @param blocked_step_id: Step that cannot be scheduled.
        @return: ReplanOutcome.
        """
        failed_step = self._find_step(plan=plan, step_id=blocked_step_id)
        decision = ReplanDecision(
            should_replan=True,
            strategy="rollback_retry",
            reason="missing_dependency",
            message=f"dependency graph blocked at {blocked_step_id}",
        )
        return self._rollback_retry(plan=plan, failed_step=failed_step, decision=decision)

    def _build_decision(self, error: Dict[str, Any], reason: str) -> ReplanDecision:
        """
        Build replan decision based on error category.

        @param error: Error payload.
        @param reason: Trigger reason.
        @return: ReplanDecision.
        """
        error_code = str((error or {}).get("code", "unknown_error"))
        if error_code in {"permission_denied", "schema_validation_error", "invalid_business_input"}:
            return ReplanDecision(
                should_replan=False,
                strategy="human_handoff",
                reason=reason,
                message=f"manual handoff required for {error_code}",
                requires_human_handoff=True,
            )

        if error_code in {"tool_timeout", "transient_network_error", "retry_exhausted", "service_unavailable"}:
            return ReplanDecision(
                should_replan=True,
                strategy="local_replace",
                reason=reason,
                message=f"retry with local replace for {error_code}",
            )

        return ReplanDecision(
            should_replan=True,
            strategy="rollback_retry",
            reason=reason,
            message=f"fallback to rollback retry for {error_code}",
        )

    def _local_replace(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep,
        decision: ReplanDecision,
    ) -> ReplanOutcome:
        """
        Replace one failed step and remap dependent steps.

        @param plan: Current execution plan.
        @param failed_step: Failed step.
        @param decision: Replan decision.
        @return: ReplanOutcome.
        """
        new_plan_version = plan.plan_version + 1
        replacement_step_id = f"{failed_step.step_id}-replan-v{new_plan_version}"
        replacement_step = replace(
            failed_step,
            step_id=replacement_step_id,
            goal=f"{failed_step.goal} (replanned)",
        )

        remapped_steps: List[PlanStep] = []
        for step in plan.steps:
            if step.step_id == failed_step.step_id:
                remapped_steps.append(replacement_step)
                continue

            remapped_dependencies = [
                replacement_step_id if dependency_step_id == failed_step.step_id else dependency_step_id
                for dependency_step_id in step.depends_on
            ]
            remapped_steps.append(replace(step, depends_on=remapped_dependencies))

        new_plan = ExecutionPlan(
            request_id=plan.request_id,
            session_id=plan.session_id,
            trace_id=plan.trace_id,
            plan_version=new_plan_version,
            steps=remapped_steps,
            risk_flags=list(plan.risk_flags),
            graph_limits=plan.graph_limits,
        )
        mapping = StepIdMapping(
            source_step_id=failed_step.step_id,
            target_step_id=replacement_step_id,
            plan_version=new_plan_version,
        )
        return ReplanOutcome(plan=new_plan, decision=decision, step_id_mappings=[mapping])

    def _rollback_retry(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep,
        decision: ReplanDecision,
    ) -> ReplanOutcome:
        """
        Rebuild the failed step and all downstream steps.

        @param plan: Current execution plan.
        @param failed_step: Failed step.
        @param decision: Replan decision.
        @return: ReplanOutcome.
        """
        new_plan_version = plan.plan_version + 1
        failed_step_index = self._find_step_index(plan=plan, step_id=failed_step.step_id)
        immutable_prefix = plan.steps[:failed_step_index]
        mutable_suffix = plan.steps[failed_step_index:]

        step_id_map: Dict[str, str] = {}
        remapped_suffix: List[PlanStep] = []
        mappings: List[StepIdMapping] = []

        for suffix_step in mutable_suffix:
            new_step_id = f"{suffix_step.step_id}-replan-v{new_plan_version}"
            step_id_map[suffix_step.step_id] = new_step_id

        for suffix_step in mutable_suffix:
            remapped_dependencies = [
                step_id_map.get(dependency_step_id, dependency_step_id)
                for dependency_step_id in suffix_step.depends_on
            ]
            new_step_id = step_id_map[suffix_step.step_id]
            remapped_step = replace(
                suffix_step,
                step_id=new_step_id,
                goal=f"{suffix_step.goal} (rollback-replan)",
                depends_on=remapped_dependencies,
            )
            remapped_suffix.append(remapped_step)
            mappings.append(
                StepIdMapping(
                    source_step_id=suffix_step.step_id,
                    target_step_id=new_step_id,
                    plan_version=new_plan_version,
                )
            )

        new_plan = ExecutionPlan(
            request_id=plan.request_id,
            session_id=plan.session_id,
            trace_id=plan.trace_id,
            plan_version=new_plan_version,
            steps=[*immutable_prefix, *remapped_suffix],
            risk_flags=list(plan.risk_flags),
            graph_limits=plan.graph_limits,
        )
        return ReplanOutcome(plan=new_plan, decision=decision, step_id_mappings=mappings)

    def _find_step(self, plan: ExecutionPlan, step_id: str) -> PlanStep:
        """
        Find step by identifier.

        @param plan: Execution plan.
        @param step_id: Target step ID.
        @return: PlanStep.
        """
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise ValueError(f"step not found for replan: {step_id}")

    def _find_step_index(self, plan: ExecutionPlan, step_id: str) -> int:
        """
        Find index of one step in ordered list.

        @param plan: Execution plan.
        @param step_id: Target step ID.
        @return: Integer index.
        """
        for index, step in enumerate(plan.steps):
            if step.step_id == step_id:
                return index
        raise ValueError(f"step index not found for replan: {step_id}")
