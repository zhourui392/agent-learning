"""
Execution engine.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from src.agent.context import ContextManager, ExecutionContext
from src.agent.planner import ExecutionPlan, PlanStep
from src.agent.policy import ToolPolicyEngine
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
        max_retry_attempts: int = 1,
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
        @param max_retry_attempts: Additional retries after initial attempt.
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
        self._max_retry_attempts = max_retry_attempts

    def execute(self, plan: ExecutionPlan, request: Mapping[str, Any], context: ExecutionContext) -> ExecutionResult:
        """
        Execute plan with resume support and normalized error model.

        @param plan: Execution plan object.
        @param request: Validated request payload.
        @param context: Runtime execution context.
        @return: ExecutionResult.
        """
        session_state = self._state_store.get_session(plan.session_id)
        recovery_point = self._recovery_service.find_recovery_point(session_state)
        completed_steps = set(recovery_point.completed_step_ids)

        self._state_store.set_session_status(plan.session_id, ExecutionStatus.RUNNING)
        step_results: List[Dict[str, Any]] = []

        for step in plan.steps:
            if step.step_id in completed_steps:
                self._audit_logger.debug("skip completed step", step_id=step.step_id)
                continue

            result = self._execute_single_step(plan=plan, step=step, request=request, context=context)
            step_results.append({"step_id": step.step_id, "tool_id": step.tool_id, "result": result})

            self._context_manager.append_step_summary(
                context=context,
                summary={"step_id": step.step_id, "tool_id": step.tool_id, "success": result.get("success")},
            )

            if not result.get("success"):
                self._state_store.set_session_status(plan.session_id, ExecutionStatus.FAILED)
                return ExecutionResult(success=False, step_results=step_results, error=result.get("error"))

        self._state_store.set_session_status(plan.session_id, ExecutionStatus.SUCCESS)
        return ExecutionResult(success=True, step_results=step_results)

    def _execute_single_step(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        request: Mapping[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """
        Execute one plan step with retry and snapshot.

        @param plan: Execution plan.
        @param step: Current plan step.
        @param request: Request payload.
        @param context: Runtime context.
        @return: Normalized tool result envelope.
        """
        attempts = 0
        while attempts <= self._max_retry_attempts:
            attempts += 1
            self._state_store.mark_step_running(plan.session_id, step.step_id)

            pre_snapshot = self._snapshot_manager.create(
                session_state=self._state_store.get_session(plan.session_id),
                step_id=step.step_id,
                phase="pre-step",
                payload={"attempt": attempts, "tool_id": step.tool_id},
            )
            self._state_store.save_snapshot(plan.session_id, pre_snapshot)

            if not self._policy_engine.is_tool_allowed(step.tool_id, request.get("allowed_tools", []), request):
                result = {
                    "success": False,
                    "data": None,
                    "error": {"code": "permission_denied", "message": f"tool not allowed: {step.tool_id}"},
                    "retryable": False,
                }
                self._state_store.mark_step_failed(plan.session_id, step.step_id, result["error"])
                return result

            schema_path = self._tool_registry.get_schema_path(step.tool_id)
            trimmed_context = self._context_manager.trim_for_tool(context=context, tool_id=step.tool_id)
            payload_with_context = dict(step.payload)
            payload_with_context["runtime_context"] = trimmed_context

            try:
                self._validator.validate(schema_path=schema_path, payload=payload_with_context)
            except ContractValidationError as error:
                result = {
                    "success": False,
                    "data": None,
                    "error": {"code": "schema_validation_error", "message": str(error)},
                    "retryable": False,
                }
                self._state_store.mark_step_failed(plan.session_id, step.step_id, result["error"])
                return result

            self._state_store.mark_step_waiting_tool(plan.session_id, step.step_id)
            started_at = time.monotonic()
            result = self._tool_registry.invoke(step.tool_id, payload_with_context)
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
                self._state_store.mark_step_success(plan.session_id, step.step_id, result)
                post_snapshot = self._snapshot_manager.create(
                    session_state=self._state_store.get_session(plan.session_id),
                    step_id=step.step_id,
                    phase="post-success",
                    payload={"attempt": attempts, "result": result},
                )
                self._state_store.save_snapshot(plan.session_id, post_snapshot)
                return result

            self._state_store.mark_step_failed(plan.session_id, step.step_id, result.get("error") or {})
            if not result.get("retryable"):
                return result

        return {
            "success": False,
            "data": None,
            "error": {"code": "retry_exhausted", "message": f"retry limit reached for step {step.step_id}"},
            "retryable": False,
        }
