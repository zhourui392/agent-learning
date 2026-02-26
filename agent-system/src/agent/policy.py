"""
Tool policy decisions.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Set


@dataclass
class ToolPermission:
    """
    Static permission metadata for one tool.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    tool_id: str
    requires_approval_token: bool = False


@dataclass
class ToolPolicyEngine:
    """
    Applies tool permission and context checks.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    permission_map: Mapping[str, ToolPermission] = field(default_factory=dict)

    def is_tool_allowed(self, tool_id: str, allowed_tools: Iterable[str], request: Mapping[str, object]) -> bool:
        """
        Check whether the tool call is allowed.

        @param tool_id: Tool identifier.
        @param allowed_tools: Tool IDs explicitly allowed by request.
        @param request: Agent request for contextual checks.
        @return: True when policy allows invocation.
        """
        allowed_set: Set[str] = set(allowed_tools)
        if tool_id not in allowed_set:
            return False

        permission = self.permission_map.get(tool_id)
        if permission is None or not permission.requires_approval_token:
            return True

        metadata = request.get("metadata", {})
        return bool(metadata.get("approval_token"))

    @classmethod
    def default(cls) -> "ToolPolicyEngine":
        """
        Build default tool policy map.

        @param cls: Class reference.
        @return: ToolPolicyEngine with default permissions.
        """
        return cls(
            permission_map={
                "tool.search": ToolPermission(tool_id="tool.search"),
                "tool.query_db": ToolPermission(tool_id="tool.query_db"),
                "tool.notify": ToolPermission(tool_id="tool.notify", requires_approval_token=True),
            }
        )
