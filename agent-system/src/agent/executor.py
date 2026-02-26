"""
Execution engine.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agent.context import ContextManager, ExecutionContext
from src.agent.execution_context import ExecutionControl
from src.agent.planner import ExecutionPlan, PlanStep
from src.agent.policy import ToolPolicyEngine
from src.agent.replanner import ReplanOutcome, Replanner
from src.gateway.audit_logger import AuditLogger
from src.gateway.validator import ContractValidationError, ContractValidator
from src.gateway.tool_registry import ToolRegistry
from src.state.recovery import RecoveryService
from src.state.snapshot import SnapshotManager
from src.state.store import ExecutionStatus, InMemoryStateStore


@dataclass
class ExecutionResult:
    """
    Aggregate result from execution engine.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    success: bool
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Dict[str, Any] | None = None
    trace_id: str = ""
    plan_version: int = 1
    replan_history: List[Dict[str, Any]] = field(default_factory=list)


class Executor:
    """
    Runs plan steps with contract checks, policy checks, and state updates.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(
        self,
        state_store: InMemoryStateStore,
        snapshot_manager: SnapshotManager,
        recovery_service: RecoveryService,
        tool_registry: ToolRegistry,
        validator: ContractValidator,
        policy_engine: ToolPolicyEngine,
        context_manager: ContextManager,
        audit_logger: AuditLogger,
        replanner: Optional[Replanner] = None,
        max_retry_attempts: int = 1,
        max_replan_attempts: int = 1,
    ) -> None:
        """
        Initialize executor dependencies.

        @param state_store: Runtime state store.
        @param snapshot_manager: Snapshot manager.
        @param recovery_service: Recovery strategy service.
        @param tool_registry: Tool invocation registry.
        @param validator: Contract validator.
        @param policy_engine: Tool policy engine.
        @param context_manager: Context manager.
        @param audit_logger: Audit logger instance.
        @param replanner: Optional replanner for failure recovery.
        @param max_retry_attempts: Additional retries after initial attempt.
        @param max_replan_attempts: Maximum replan count per execution.
        @return: None.
        """
        self._state_store = state_store
        self._snapshot_manager = snapshot_manager
        self._recovery_service = recovery_service
        self._tool_registry = tool_registry
        self._validator = validator
        self._policy_engine = policy_engine
        self._context_manager = context_manager
        self._audit_logger = audit_logger
        self._replanner = replanner
        self._max_retry_attempts = max_retry_attempts
        self._max_replan_attempts = max_replan_attempts

    def execute(
        self,
        plan: ExecutionPlan,
        request: Mapping[str, Any],
        context: ExecutionContext,
        control: Optional[ExecutionControl] = None,
    ) -> ExecutionResult:
        """
        Execute plan with resume support, timeout, cancel, retry, and replan.

        @param plan: Execution plan object.
        @param request: Validated request payload.
        @param context: Runtime execution context.
        @param control: Optional runtime control object.
        @return: ExecutionResult.
        """
        runtime_control = control or ExecutionControl()
        self._state_store.init_session(
            request_id=plan.request_id,
            session_id=plan.session_id,
            steps=self._serialize_plan_steps(plan.steps),
            plan_version=plan.plan_version,
            trace_id=plan.trace_id,
        )

        session_state = self._state_store.get_session(plan.session_id)
        recovery_point = self._recovery_service.find_recovery_point(session_state)
        completed_steps = set(recovery_point.completed_step_ids)

        self._state_store.set_session_status(plan.session_id, ExecutionStatus.RUNNING)
        step_results: List[Dict[str, Any]] = []
        replan_history: List[Dict[str, Any]] = []

        current_plan = plan
        replan_count = 0

        while True:
            if self._is_cancelled(runtime_control=runtime_control, session_id=current_plan.session_id):
                error = {
                    "code": "session_cancelled",
                    "message": "execution cancelled by control signal",
                }
                self._state_store.set_session_status(current_plan.session_id, ExecutionStatus.CANCELED)
                return ExecutionResult(
                    success=False,
                    step_results=step_results,
                    error=error,
                    trace_id=current_plan.trace_id,
                    plan_version=current_plan.plan_version,
                    replan_history=replan_history,
                )

            if runtime_control.is_session_timed_out():
                error = {
                    "code": "session_timeout",
                    "message": "execution exceeded session timeout",
                }
                self._state_store.set_session_status(current_plan.session_id, ExecutionStatus.FAILED)
                return ExecutionResult(
                    success=False,
                    step_results=step_results,
                    error=error,
                    trace_id=current_plan.trace_id,
                    plan_version=current_plan.plan_version,
                    replan_history=replan_history,
                )

            pending_steps = [
                step
                for step in current_plan.steps
                if step.step_id not in completed_steps
            ]
            if not pending_steps:
                self._state_store.set_session_status(current_plan.session_id, ExecutionStatus.SUCCESS)
                self._save_snapshot(
                    plan=current_plan,
                    step_id="final",
                    phase="final-response",
                    payload={"step_results": len(step_results), "replan_count": replan_count},
                )
                return ExecutionResult(
                    success=True,
                    step_results=step_results,
                    error=None,
                    trace_id=current_plan.trace_id,
                    plan_version=current_plan.plan_version,
                    replan_history=replan_history,
                )

            ready_steps = [
                step
                for step in pending_steps
                if all(dependency_step_id in completed_steps for dependency_step_id in step.depends_on)
            ]

            if not ready_steps:
                replan_outcome = self._replan_for_missing_dependency(
                    current_plan=current_plan,
                    pending_steps=pending_steps,
                    replan_count=replan_count,
                )
                if replan_outcome is None:
                    error = {
                        "code": "dependency_blocked",
                        "message": "no executable step and replanner not available",
                    }
                    self._state_store.set_session_status(current_plan.session_id, ExecutionStatus.FAILED)
                    return ExecutionResult(
                        success=False,
                        step_results=step_results,
                        error=error,
                        trace_id=current_plan.trace_id,
                        plan_version=current_plan.plan_version,
                        replan_history=replan_history,
                    )

                current_plan = replan_outcome.plan
                replan_count += 1
                replan_history.append(self._build_replan_history_item(replan_outcome))
                self._state_store.upsert_plan_steps(
                    session_id=current_plan.session_id,
                    steps=self._serialize_plan_steps(current_plan.steps),
                    plan_version=current_plan.plan_version,
                )
                continue

            max_parallel = min(runtime_control.max_concurrency, current_plan.graph_limits.max_parallel)
            runnable_steps = ready_steps[:max_parallel]
            batch_results = self._execute_ready_steps(
                plan=current_plan,
                steps=runnable_steps,
                request=request,
                context=context,
                control=runtime_control,
            )

            should_continue_with_replan = False
            for step_outcome in batch_results:
                step = step_outcome["step"]
                result = step_outcome["result"]
                step_results.append(
                    {
                        "step_id": step.step_id,
                        "tool_id": step.tool_id,
                        "plan_version": current_plan.plan_version,
                        "result": result,
                    }
                )
                self._context_manager.append_step_summary(
                    context=context,
                    summary={
                        "step_id": step.step_id,
                        "tool_id": step.tool_id,
                        "success": result.get("success"),
                    },
                )

                if result.get("success"):
                    completed_steps.add(step.step_id)
                    continue

                replan_outcome = self._replan_after_failure(
                    current_plan=current_plan,
                    failed_step=step,
                    error=result.get("error") or {},
                    replan_count=replan_count,
                )
                if replan_outcome is not None:
                    current_plan = replan_outcome.plan
                    replan_count += 1
                    replan_history.append(self._build_replan_history_item(replan_outcome))
                    self._state_store.upsert_plan_steps(
                        session_id=current_plan.session_id,
                        steps=self._serialize_plan_steps(current_plan.steps),
                        plan_version=current_plan.plan_version,
                    )
                    should_continue_with_replan = True
                    break

                self._state_store.set_session_status(current_plan.session_id, ExecutionStatus.FAILED)
                return ExecutionResult(
                    success=False,
                    step_results=step_results,
                    error=result.get("error"),
                    trace_id=current_plan.trace_id,
                    plan_version=current_plan.plan_version,
                    replan_history=replan_history,
                )

            if should_continue_with_replan:
                continue

    def _execute_ready_steps(
        self,
        plan: ExecutionPlan,
        steps: Sequence[PlanStep],
        request: Mapping[str, Any],
        context: ExecutionContext,
        control: ExecutionControl,
    ) -> List[Dict[str, Any]]:
        """
        Execute one ready batch with mixed serial/parallel scheduling.

        @param plan: Current plan.
        @param steps: Ready steps for this round.
        @param request: Request payload.
        @param context: Runtime context.
        @param control: Execution controls.
        @return: Ordered step outcomes.
        """
        if not steps:
            return []

        results_by_step_id: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=len(steps)) as batch_pool:
            future_map = {
                batch_pool.submit(
                    self._execute_single_step,
                    plan,
                    step,
                    request,
                    context,
                    control,
                ): step
                for step in steps
            }
            for future in as_completed(future_map):
                step = future_map[future]
                try:
                    result = future.result()
                except Exception as error:  # pragma: no cover - defensive guard
                    result = {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "executor_internal_error",
                            "message": str(error),
                        },
                        "retryable": False,
                    }
                results_by_step_id[step.step_id] = {"step": step, "result": result}

        ordered_results: List[Dict[str, Any]] = []
        for step in steps:
            ordered_results.append(results_by_step_id[step.step_id])
        return ordered_results

    def _execute_single_step(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        request: Mapping[str, Any],
        context: ExecutionContext,
        control: ExecutionControl,
    ) -> Dict[str, Any]:
        """
        Execute one plan step with retry, timeout, idempotency, and snapshot.

        @param plan: Execution plan.
        @param step: Current plan step.
        @param request: Request payload.
        @param context: Runtime context.
        @param control: Execution controls.
        @return: Normalized tool result envelope.
        """
        idempotency_key = self._state_store.build_idempotency_key(
            request_id=plan.request_id,
            step_id=step.step_id,
            version=plan.plan_version,
        )
        if self._state_store.should_skip_step(plan.session_id, step.step_id, idempotency_key):
            self._audit_logger.debug(
                "skip step by idempotency",
                session_id=plan.session_id,
                step_id=step.step_id,
                idempotency_key=idempotency_key,
            )
            cached_result = self._state_store.get_step_result(plan.session_id, step.step_id)
            return cached_result or {
                "success": True,
                "data": {"idempotent_skip": True},
                "error": None,
                "retryable": False,
            }

        last_retryable_result: Optional[Dict[str, Any]] = None
        max_attempts = self._max_retry_attempts + 1
        for attempt in range(1, max_attempts + 1):
            if self._is_cancelled(runtime_control=control, session_id=plan.session_id):
                cancel_error = {"code": "step_cancelled", "message": f"step cancelled: {step.step_id}"}
                self._state_store.mark_step_canceled(plan.session_id, step.step_id, cancel_error)
                return {
                    "success": False,
                    "data": None,
                    "error": cancel_error,
                    "retryable": False,
                }

            self._state_store.mark_step_running(plan.session_id, step.step_id)
            self._save_snapshot(
                plan=plan,
                step_id=step.step_id,
                phase="pre-step",
                payload={"attempt": attempt, "tool_id": step.tool_id, "idempotency_key": idempotency_key},
            )

            policy_result = self._check_policy(step=step, request=request)
            if policy_result is not None:
                self._state_store.mark_step_failed(plan.session_id, step.step_id, policy_result["error"])
                self._save_snapshot(
                    plan=plan,
                    step_id=step.step_id,
                    phase="post-failed",
                    payload={"attempt": attempt, "result": policy_result},
                )
                return policy_result

            payload_with_context = self._build_payload_with_context(context=context, step=step)
            schema_result = self._check_schema(step=step, payload_with_context=payload_with_context)
            if schema_result is not None:
                self._state_store.mark_step_failed(plan.session_id, step.step_id, schema_result["error"])
                self._save_snapshot(
                    plan=plan,
                    step_id=step.step_id,
                    phase="post-failed",
                    payload={"attempt": attempt, "result": schema_result},
                )
                return schema_result

            self._state_store.mark_step_waiting_tool(plan.session_id, step.step_id)
            timeout_seconds = step.timeout_seconds if step.timeout_seconds > 0 else control.default_step_timeout_seconds
            started_at = time.monotonic()
            result = self._invoke_tool_with_timeout(
                tool_id=step.tool_id,
                payload_with_context=payload_with_context,
                timeout_seconds=timeout_seconds,
            )
            duration_ms = int((time.monotonic() - started_at) * 1000)

            self._audit_logger.log_step_event(
                request_id=plan.request_id,
                session_id=plan.session_id,
                step_id=step.step_id,
                tool_id=step.tool_id,
                duration_ms=duration_ms,
                result=result,
            )

            if result.get("success"):
                self._state_store.mark_step_success(
                    session_id=plan.session_id,
                    step_id=step.step_id,
                    result=result,
                    idempotency_key=idempotency_key,
                )
                self._save_snapshot(
                    plan=plan,
                    step_id=step.step_id,
                    phase="post-success",
                    payload={"attempt": attempt, "result": result},
                )
                return result

            self._state_store.mark_step_failed(plan.session_id, step.step_id, result.get("error") or {})
            self._save_snapshot(
                plan=plan,
                step_id=step.step_id,
                phase="post-failed",
                payload={"attempt": attempt, "result": result},
            )

            if not result.get("retryable"):
                return result
            last_retryable_result = result

        exhausted_result = {
            "success": False,
            "data": None,
            "error": {
                "code": "retry_exhausted",
                "message": f"retry limit reached for step {step.step_id}",
                "last_error": (last_retryable_result or {}).get("error"),
            },
            "retryable": False,
        }
        self._state_store.mark_step_failed(plan.session_id, step.step_id, exhausted_result["error"])
        self._save_snapshot(
            plan=plan,
            step_id=step.step_id,
            phase="post-failed",
            payload={"attempt": max_attempts, "result": exhausted_result},
        )
        return exhausted_result

    def _check_policy(self, step: PlanStep, request: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate policy constraints for a step.

        @param step: Plan step.
        @param request: Original request payload.
        @return: Failure envelope when denied, else None.
        """
        if self._policy_engine.is_tool_allowed(step.tool_id, request.get("allowed_tools", []), request):
            return None
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "permission_denied",
                "message": f"tool not allowed: {step.tool_id}",
            },
            "retryable": False,
        }

    def _check_schema(self, step: PlanStep, payload_with_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate tool payload schema.

        @param step: Plan step.
        @param payload_with_context: Tool payload with runtime context.
        @return: Failure envelope when schema fails, else None.
        """
        schema_path = self._tool_registry.get_schema_path(step.tool_id)
        try:
            self._validator.validate(schema_path=schema_path, payload=payload_with_context)
            return None
        except ContractValidationError as error:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "schema_validation_error",
                    "message": str(error),
                },
                "retryable": False,
            }

    def _build_payload_with_context(self, context: ExecutionContext, step: PlanStep) -> Dict[str, Any]:
        """
        Build tool payload with trimmed runtime context.

        @param context: Runtime context.
        @param step: Plan step.
        @return: Payload with runtime context.
        """
        trimmed_context = self._context_manager.trim_for_tool(context=context, tool_id=step.tool_id)
        payload_with_context = dict(step.payload)
        payload_with_context["runtime_context"] = trimmed_context
        return payload_with_context

    def _invoke_tool_with_timeout(
        self,
        tool_id: str,
        payload_with_context: Dict[str, Any],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        """
        Invoke tool with timeout protection.

        @param tool_id: Tool identifier.
        @param payload_with_context: Validated payload.
        @param timeout_seconds: Timeout in seconds.
        @return: Normalized tool result envelope.
        """
        invoke_pool = ThreadPoolExecutor(max_workers=1)
        future = invoke_pool.submit(self._tool_registry.invoke, tool_id, payload_with_context)
        try:
            result = future.result(timeout=timeout_seconds)
            invoke_pool.shutdown(wait=True)
            return result
        except FuturesTimeoutError:
            future.cancel()
            invoke_pool.shutdown(wait=False, cancel_futures=True)
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "tool_timeout",
                    "message": f"tool timeout after {timeout_seconds}s",
                },
                "retryable": True,
            }
        except Exception as error:  # pragma: no cover - defensive fallback
            future.cancel()
            invoke_pool.shutdown(wait=False, cancel_futures=True)
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "tool_runtime_exception",
                    "message": str(error),
                },
                "retryable": False,
            }

    def _replan_for_missing_dependency(
        self,
        current_plan: ExecutionPlan,
        pending_steps: Sequence[PlanStep],
        replan_count: int,
    ) -> Optional[ReplanOutcome]:
        """
        Trigger replanner when dependency graph is blocked.

        @param current_plan: Current plan.
        @param pending_steps: Steps still pending.
        @param replan_count: Current replan count.
        @return: ReplanOutcome when replan is applied.
        """
        if self._replanner is None or replan_count >= self._max_replan_attempts:
            return None
        blocked_step = pending_steps[0]
        return self._replanner.replan_for_missing_dependency(
            plan=current_plan,
            blocked_step_id=blocked_step.step_id,
        )

    def _replan_after_failure(
        self,
        current_plan: ExecutionPlan,
        failed_step: PlanStep,
        error: Dict[str, Any],
        replan_count: int,
    ) -> Optional[ReplanOutcome]:
        """
        Trigger replanner for failed step.

        @param current_plan: Current plan.
        @param failed_step: Failed step.
        @param error: Step error payload.
        @param replan_count: Current replan count.
        @return: ReplanOutcome when replan is applied.
        """
        if self._replanner is None or replan_count >= self._max_replan_attempts:
            return None

        replan_outcome = self._replanner.replan_after_failure(
            plan=current_plan,
            failed_step=failed_step,
            error=error,
        )
        if replan_outcome.decision.requires_human_handoff:
            return None
        if not replan_outcome.decision.should_replan:
            return None
        return replan_outcome

    def _save_snapshot(self, plan: ExecutionPlan, step_id: str, phase: str, payload: Dict[str, Any]) -> None:
        """
        Build and persist snapshot for one execution boundary.

        @param plan: Execution plan.
        @param step_id: Step identifier.
        @param phase: Snapshot phase.
        @param payload: Snapshot payload.
        @return: None.
        """
        snapshot = self._snapshot_manager.create(
            session_state=self._state_store.get_session(plan.session_id),
            step_id=step_id,
            phase=phase,
            payload=payload,
        )
        self._state_store.save_snapshot(plan.session_id, snapshot)

    def _is_cancelled(self, runtime_control: ExecutionControl, session_id: str) -> bool:
        """
        Check cancellation signals from control and store.

        @param runtime_control: Execution control object.
        @param session_id: Session identifier.
        @return: True when cancellation is requested.
        """
        if runtime_control.is_cancelled():
            return True
        return self._state_store.is_cancel_requested(session_id)

    def _serialize_plan_steps(self, steps: Sequence[PlanStep]) -> List[Dict[str, Any]]:
        """
        Convert step objects to store-ready dictionaries.

        @param steps: Plan steps.
        @return: Serialized step dictionaries.
        """
        serialized: List[Dict[str, Any]] = []
        for step in steps:
            serialized.append(
                {
                    "step_id": step.step_id,
                    "tool_id": step.tool_id,
                    "goal": step.goal,
                    "depends_on": list(step.depends_on),
                }
            )
        return serialized

    def _build_replan_history_item(self, replan_outcome: ReplanOutcome) -> Dict[str, Any]:
        """
        Build serializable replan history item.

        @param replan_outcome: Replan outcome.
        @return: Replan history dictionary.
        """
        return {
            "strategy": replan_outcome.decision.strategy,
            "reason": replan_outcome.decision.reason,
            "message": replan_outcome.decision.message,
            "target_plan_version": replan_outcome.plan.plan_version,
            "step_id_mapping": [
                {
                    "source_step_id": item.source_step_id,
                    "target_step_id": item.target_step_id,
                    "plan_version": item.plan_version,
                }
                for item in replan_outcome.step_id_mappings
            ],
        }
