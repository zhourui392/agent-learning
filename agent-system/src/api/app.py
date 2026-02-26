"""
Application entry for local architecture baseline.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping

from src.agent.context import ContextManager
from src.agent.execution_context import ExecutionControl
from src.agent.executor import Executor
from src.agent.planner import Planner
from src.agent.policy import ToolPolicyEngine
from src.agent.replanner import Replanner
from src.gateway.audit_logger import AuditLogger
from src.gateway.tool_registry import ToolDefinition, ToolExecutionError, ToolRegistry
from src.gateway.validator import ContractValidationError, ContractValidator
from src.state.recovery import RecoveryService
from src.state.snapshot import SnapshotManager
from src.state.store import InMemoryStateStore


class AgentApplication:
    """
    Composes planner, executor, replanner, gateway, and state store.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, project_root: Path) -> None:
        """
        Initialize application dependencies.

        @param project_root: Root directory of the project.
        @return: None.
        """
        self._project_root = project_root
        self._validator = ContractValidator(contracts_root=project_root / "contracts")
        self._registry = ToolRegistry()
        self._policy_engine = ToolPolicyEngine.default()
        self._context_manager = ContextManager()
        self._planner = Planner()

        self._state_store = InMemoryStateStore()
        self._snapshot_manager = SnapshotManager()
        self._recovery_service = RecoveryService()
        self._replanner = Replanner()

        self._audit_logger = AuditLogger(log_file=project_root / "logs" / "audit.log")
        self._executor = Executor(
            state_store=self._state_store,
            snapshot_manager=self._snapshot_manager,
            recovery_service=self._recovery_service,
            tool_registry=self._registry,
            validator=self._validator,
            policy_engine=self._policy_engine,
            context_manager=self._context_manager,
            audit_logger=self._audit_logger,
            replanner=self._replanner,
            max_retry_attempts=1,
            max_replan_attempts=1,
        )
        self._tool_behavior_counters: Dict[str, int] = {}
        self._register_tools()

    def handle_request(self, request_payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Run full request lifecycle and return validated response.

        @param request_payload: Request payload from API layer.
        @return: Agent response payload.
        """
        started_at = time.monotonic()
        self._validator.validate_request(request_payload)

        context = self._context_manager.build(request_payload)
        plan = self._planner.create_plan(request_payload)
        execution_control = ExecutionControl.from_request(request_payload)

        self._state_store.init_session(
            request_id=plan.request_id,
            session_id=plan.session_id,
            trace_id=plan.trace_id,
            plan_version=plan.plan_version,
            steps=[
                {
                    "step_id": step.step_id,
                    "tool_id": step.tool_id,
                    "goal": step.goal,
                    "depends_on": list(step.depends_on),
                }
                for step in plan.steps
            ],
        )

        execution_result = self._executor.execute(
            plan=plan,
            request=request_payload,
            context=context,
            control=execution_control,
        )
        response_payload = {
            "request_id": plan.request_id,
            "session_id": plan.session_id,
            "success": execution_result.success,
            "data": (
                {
                    "trace_id": execution_result.trace_id,
                    "plan_version": execution_result.plan_version,
                    "risk_flags": list(plan.risk_flags),
                    "replan_history": execution_result.replan_history,
                    "step_results": execution_result.step_results,
                }
                if execution_result.success
                else None
            ),
            "error": execution_result.error,
        }

        self._validator.validate_response(response_payload)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        self._audit_logger.log_final_event(
            request_id=plan.request_id,
            session_id=plan.session_id,
            success=execution_result.success,
            duration_ms=duration_ms,
        )
        return response_payload

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any] | None:
        """
        Get latest snapshot for debug replay.

        @param session_id: Session identifier.
        @return: Latest snapshot or None.
        """
        return self._state_store.latest_snapshot(session_id)

    def _register_tools(self) -> None:
        """
        Register mock tools for local end-to-end flow.

        @param self: Application instance.
        @return: None.
        """
        self._registry.register(
            ToolDefinition(
                tool_id="tool.search",
                schema_path="tools/tool.search.schema.json",
                handler=self._tool_search,
            )
        )
        self._registry.register(
            ToolDefinition(
                tool_id="tool.query_db",
                schema_path="tools/tool.query_db.schema.json",
                handler=self._tool_query_db,
            )
        )
        self._registry.register(
            ToolDefinition(
                tool_id="tool.notify",
                schema_path="tools/tool.notify.schema.json",
                handler=self._tool_notify,
            )
        )

    def _tool_search(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Mock search tool handler.

        @param payload: Validated search payload.
        @return: Search result payload.
        """
        query = str(payload.get("query", "")).strip().lower()
        if "sleep_short" in query:
            time.sleep(1.5)

        if "timeout" in query:
            raise ToolExecutionError(code="tool_timeout", message="search timeout", retryable=True)

        if "flaky_once" in query and self._should_fail_once(f"search:{query}"):
            raise ToolExecutionError(
                code="transient_network_error",
                message="temporary search failure",
                retryable=True,
            )

        if "flaky_twice" in query and self._should_fail_twice(f"search:{query}"):
            raise ToolExecutionError(
                code="service_unavailable",
                message="temporary upstream outage",
                retryable=True,
            )

        if "force_fail" in query:
            raise ToolExecutionError(
                code="invalid_business_input",
                message="search input is invalid",
                retryable=False,
            )

        return {
            "query": payload.get("query"),
            "items": [
                {"title": "Architecture Baseline", "score": 0.88},
                {"title": "Recovery Design", "score": 0.75},
            ][: int(payload.get("top_k", 2))],
        }

    def _tool_query_db(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Mock query_db tool handler.

        @param payload: Validated query payload.
        @return: Query result payload.
        """
        sql = str(payload.get("sql", "")).strip().lower()
        if not sql.startswith("select"):
            raise ToolExecutionError(code="invalid_business_input", message="only SELECT is allowed", retryable=False)

        if "transient_fail_once" in sql and self._should_fail_once(f"query:{sql}"):
            raise ToolExecutionError(
                code="service_unavailable",
                message="db service unavailable",
                retryable=True,
            )

        return {"rows": [{"ok": 1}], "row_count": 1, "limit": payload.get("limit", 10)}

    def _tool_notify(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Mock notify tool handler.

        @param payload: Validated notify payload.
        @return: Notify result payload.
        """
        message = str(payload.get("message", ""))
        if len(message) > 500:
            raise ToolExecutionError(code="invalid_business_input", message="message too long", retryable=False)

        if "handoff" in message.lower():
            raise ToolExecutionError(
                code="permission_denied",
                message="manual approval required",
                retryable=False,
            )

        return {
            "channel": payload.get("channel"),
            "recipient": payload.get("recipient"),
            "status": "queued",
        }

    def _should_fail_once(self, key: str) -> bool:
        """
        Return True on first call for a key and False afterwards.

        @param key: Behavior key.
        @return: Boolean flag for first-call failure.
        """
        current = self._tool_behavior_counters.get(key, 0)
        self._tool_behavior_counters[key] = current + 1
        return current == 0

    def _should_fail_twice(self, key: str) -> bool:
        """
        Return True on first two calls for a key and False afterwards.

        @param key: Behavior key.
        @return: Boolean flag for two-call failure window.
        """
        current = self._tool_behavior_counters.get(key, 0)
        self._tool_behavior_counters[key] = current + 1
        return current < 2


def _read_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Read JSON payload from file.

    @param file_path: Input JSON file path.
    @return: Parsed JSON dictionary.
    """
    with file_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def main() -> None:
    """
    CLI entry for local request replay.

    @param: None.
    @return: None.
    """
    parser = argparse.ArgumentParser(description="Run local agent architecture baseline")
    parser.add_argument(
        "--request-file",
        type=str,
        default="tests/fixtures/sample_request.json",
        help="Path to request JSON file relative to project root.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    request_path = project_root / args.request_file

    app = AgentApplication(project_root=project_root)
    request_payload = _read_json_file(request_path)

    try:
        response = app.handle_request(request_payload)
    except ContractValidationError as error:
        print(json.dumps({"success": False, "error": {"code": "contract_error", "message": str(error)}}))
        return

    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
