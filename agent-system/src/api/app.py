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
from src.agent.executor import Executor
from src.agent.planner import Planner
from src.agent.policy import ToolPolicyEngine
from src.gateway.audit_logger import AuditLogger
from src.gateway.tool_registry import ToolDefinition, ToolExecutionError, ToolRegistry
from src.gateway.validator import ContractValidationError, ContractValidator
from src.state.recovery import RecoveryService
from src.state.snapshot import SnapshotManager
from src.state.store import InMemoryStateStore


class AgentApplication:
    """
    Composes planner, executor, gateway, and state store.

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
            max_retry_attempts=1,
        )
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

        self._state_store.init_session(
            request_id=plan.request_id,
            session_id=plan.session_id,
            steps=[{"step_id": step.step_id, "tool_id": step.tool_id} for step in plan.steps],
        )

        execution_result = self._executor.execute(plan=plan, request=request_payload, context=context)
        response_payload = {
            "request_id": plan.request_id,
            "session_id": plan.session_id,
            "success": execution_result.success,
            "data": {"step_results": execution_result.step_results} if execution_result.success else None,
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
        query = str(payload.get("query", "")).lower()
        if "timeout" in query:
            raise ToolExecutionError(code="tool_timeout", message="search timeout", retryable=True)

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

        return {
            "channel": payload.get("channel"),
            "recipient": payload.get("recipient"),
            "status": "queued",
        }


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
