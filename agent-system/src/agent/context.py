"""
Execution context model.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

REDACTED_FIELDS = {"api_key", "password", "access_token", "ssn", "phone"}


@dataclass
class SystemContext:
    """
    Runtime-level metadata for policy and routing.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    tenant_id: str
    environment: str
    policy_version: str


@dataclass
class TaskContext:
    """
    Request-level task information.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    request_id: str
    session_id: str
    user_input: str


@dataclass
class ToolContext:
    """
    Tool invocation state.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    current_tool: str = ""
    retry_budget: int = 1
    validated_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionMemory:
    """
    Session-level memory for replay and recovery.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    step_summaries: List[Dict[str, Any]] = field(default_factory=list)
    snapshots: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionContext:
    """
    Full context container used by planner and executor.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    system: SystemContext
    task: TaskContext
    tool: ToolContext
    memory: SessionMemory
    source_map: Dict[str, str] = field(default_factory=dict)
    trim_policy: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Builds and trims execution context.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    DEFAULT_MAX_STEP_SUMMARIES = 5

    def build(self, request: Mapping[str, Any]) -> ExecutionContext:
        """
        Build layered context from a validated request.

        @param request: Validated request payload.
        @return: ExecutionContext with source trace metadata.
        """
        self._validate_request_fields(request)

        system_context = request.get("context", {}).get("system", {})
        task_context = TaskContext(
            request_id=request["request_id"],
            session_id=request["session_id"],
            user_input=request["user_input"],
        )

        context = ExecutionContext(
            system=SystemContext(
                tenant_id=system_context.get("tenant_id", "default-tenant"),
                environment=system_context.get("environment", "local"),
                policy_version=system_context.get("policy_version", "v1"),
            ),
            task=task_context,
            tool=ToolContext(),
            memory=SessionMemory(),
            source_map={
                "request_id": "request.request_id",
                "session_id": "request.session_id",
                "user_input": "request.user_input",
                "tenant_id": "request.context.system.tenant_id",
            },
            trim_policy={"max_step_summaries": self.DEFAULT_MAX_STEP_SUMMARIES},
        )
        return context

    def trim_for_tool(self, context: ExecutionContext, tool_id: str) -> Dict[str, Any]:
        """
        Produce a trimmed and redacted dictionary for a tool call.

        @param context: Runtime execution context.
        @param tool_id: Tool identifier.
        @return: Trimmed context dictionary for safe transport.
        """
        trimmed_memory = context.memory.step_summaries[-self.DEFAULT_MAX_STEP_SUMMARIES :]
        redacted_summaries = [self._redact(summary) for summary in trimmed_memory]

        return {
            "task": {
                "request_id": context.task.request_id,
                "session_id": context.task.session_id,
                "user_input": context.task.user_input,
            },
            "system": {
                "tenant_id": context.system.tenant_id,
                "environment": context.system.environment,
                "policy_version": context.system.policy_version,
            },
            "tool": {"tool_id": tool_id, "retry_budget": context.tool.retry_budget},
            "memory": redacted_summaries,
            "source_map": context.source_map,
            "trim_policy": context.trim_policy,
        }

    def append_step_summary(self, context: ExecutionContext, summary: Dict[str, Any]) -> None:
        """
        Append step summary and enforce memory budget.

        @param context: Runtime execution context.
        @param summary: Step summary object.
        @return: None.
        """
        context.memory.step_summaries.append(self._redact(summary))
        max_items = context.trim_policy.get("max_step_summaries", self.DEFAULT_MAX_STEP_SUMMARIES)
        if len(context.memory.step_summaries) > max_items:
            context.memory.step_summaries = context.memory.step_summaries[-max_items:]

    def _validate_request_fields(self, request: Mapping[str, Any]) -> None:
        """
        Guard mandatory fields for context creation.

        @param request: Request payload.
        @return: None.
        """
        for required_field in ("request_id", "session_id", "user_input"):
            if required_field not in request or not request[required_field]:
                raise ValueError(f"missing required field: {required_field}")

    def _redact(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive keys recursively.

        @param payload: Dictionary-like payload.
        @return: Redacted dictionary.
        """
        sanitized: Dict[str, Any] = {}
        for key, value in payload.items():
            if key in REDACTED_FIELDS:
                sanitized[key] = "***"
                continue
            if isinstance(value, dict):
                sanitized[key] = self._redact(value)
                continue
            sanitized[key] = value
        return sanitized
