"""
Tool registry and invoker.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping


class ToolRegistryError(Exception):
    """
    Base registry error.

    @author zhourui(V33215020)
    @since 2026/02/26
    """


class ToolExecutionError(ToolRegistryError):
    """
    Error raised when tool execution fails.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self, code: str, message: str, retryable: bool) -> None:
        """
        Build tool execution error.

        @param code: Machine-readable error code.
        @param message: Human-readable error message.
        @param retryable: Retryability flag.
        @return: None.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class ToolDefinition:
    """
    Tool metadata and runtime handler.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    tool_id: str
    schema_path: str
    handler: Callable[[Mapping[str, Any]], Dict[str, Any]]


class ToolRegistry:
    """
    Registry responsible for tool lookup and invocation.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    def __init__(self) -> None:
        """
        Initialize empty registry.

        @param self: Registry instance.
        @return: None.
        """
        self._definitions: Dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        """
        Register one tool definition.

        @param definition: Tool metadata and handler.
        @return: None.
        """
        if definition.tool_id in self._definitions:
            raise ToolRegistryError(f"duplicate tool registration: {definition.tool_id}")
        self._definitions[definition.tool_id] = definition

    def get_schema_path(self, tool_id: str) -> str:
        """
        Resolve schema path for tool.

        @param tool_id: Tool identifier.
        @return: Contract schema path.
        """
        definition = self._get(tool_id)
        return definition.schema_path

    def invoke(self, tool_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Invoke tool and normalize envelope.

        @param tool_id: Tool identifier.
        @param payload: Validated payload.
        @return: Normalized envelope with success/data/error/retryable.
        """
        definition = self._get(tool_id)
        try:
            data = definition.handler(payload)
            return {"success": True, "data": data, "error": None, "retryable": False}
        except ToolExecutionError as error:
            return {
                "success": False,
                "data": None,
                "error": {"code": error.code, "message": error.message},
                "retryable": error.retryable,
            }
        except Exception as error:  # pragma: no cover - defensive fallback for unknown handlers
            return {
                "success": False,
                "data": None,
                "error": {"code": "tool_runtime_exception", "message": str(error)},
                "retryable": False,
            }

    def _get(self, tool_id: str) -> ToolDefinition:
        """
        Lookup tool definition.

        @param tool_id: Tool identifier.
        @return: ToolDefinition.
        """
        if tool_id not in self._definitions:
            raise ToolRegistryError(f"tool not registered: {tool_id}")
        return self._definitions[tool_id]
