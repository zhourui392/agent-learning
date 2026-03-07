"""Authorization module - role/scene/tenant based access control.

Implements:
- Role-based access control (RBAC) with hierarchical roles
- Tenant-level tool allow/deny lists
- Sensitive tool confirmation gate
- Default-deny policy
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.gateway.errors import (
    SENSITIVE_TOOL_UNCONFIRMED,
    TENANT_DENIED,
    UNAUTHORIZED,
    AuthError,
)
from src.gateway.tool_registry import ToolMeta


class Role(Enum):
    """Hierarchical role definitions. Higher ordinal = more privilege."""
    PUBLIC = "public"
    INTERNAL = "internal"
    ADMIN = "admin"


# Role hierarchy: each role includes all lower roles' permissions
_ROLE_HIERARCHY: Dict[Role, Set[Role]] = {
    Role.PUBLIC: {Role.PUBLIC},
    Role.INTERNAL: {Role.PUBLIC, Role.INTERNAL},
    Role.ADMIN: {Role.PUBLIC, Role.INTERNAL, Role.ADMIN},
}


@dataclass
class CallerIdentity:
    """Represents the identity of a tool caller."""
    caller_id: str
    role: Role = Role.PUBLIC
    tenant: str = "default"
    confirmed_tools: Set[str] = field(default_factory=set)


@dataclass
class AuthDecision:
    """Result of an authorization check."""
    allowed: bool
    reason: str = ""
    requires_confirmation: bool = False


class TenantPolicy:
    """Per-tenant tool access policy."""

    def __init__(self):
        # {tenant: set of allowed tool names} — empty means allow all
        self._allow_lists: Dict[str, Set[str]] = {}
        # {tenant: set of denied tool names}
        self._deny_lists: Dict[str, Set[str]] = {}

    def set_allow_list(self, tenant: str, tools: List[str]):
        self._allow_lists[tenant] = set(tools)

    def set_deny_list(self, tenant: str, tools: List[str]):
        self._deny_lists[tenant] = set(tools)

    def is_allowed(self, tenant: str, tool_name: str) -> bool:
        """Check tenant-level access. Deny list takes precedence over allow list."""
        if tenant in self._deny_lists and tool_name in self._deny_lists[tenant]:
            return False
        if tenant in self._allow_lists:
            return tool_name in self._allow_lists[tenant]
        return True  # No policy = allow


class ToolAuthorizer:
    """Central authorization engine for tool invocations.

    Checks are evaluated in order:
    1. Role-based access (RBAC with hierarchy)
    2. Tenant-level policy (allow/deny lists)
    3. Sensitive tool confirmation gate
    """

    def __init__(self, tenant_policy: Optional[TenantPolicy] = None):
        self._tenant_policy = tenant_policy or TenantPolicy()
        # Audit log for denied attempts
        self._denial_log: List[Dict[str, Any]] = []

    @property
    def tenant_policy(self) -> TenantPolicy:
        return self._tenant_policy

    @property
    def denial_log(self) -> List[Dict[str, Any]]:
        return list(self._denial_log)

    def authorize(self, caller: CallerIdentity, tool: ToolMeta) -> AuthDecision:
        """Run all authorization checks. Returns AuthDecision.

        Default-deny: if any check fails, access is denied.
        """
        # 1. Role check
        decision = self._check_role(caller, tool)
        if not decision.allowed:
            self._record_denial(caller, tool, decision.reason)
            return decision

        # 2. Tenant check
        decision = self._check_tenant(caller, tool)
        if not decision.allowed:
            self._record_denial(caller, tool, decision.reason)
            return decision

        # 3. Sensitive tool confirmation
        decision = self._check_sensitive(caller, tool)
        if not decision.allowed:
            self._record_denial(caller, tool, decision.reason)
            return decision

        return AuthDecision(allowed=True)

    def _check_role(self, caller: CallerIdentity, tool: ToolMeta) -> AuthDecision:
        """Verify caller's role satisfies tool's required_roles."""
        caller_roles = _ROLE_HIERARCHY.get(caller.role, {caller.role})

        for required in tool.required_roles:
            try:
                required_role = Role(required)
            except ValueError:
                # Unknown role in tool config — default deny
                return AuthDecision(
                    allowed=False,
                    reason=f"Unknown required role '{required}' in tool config.",
                )
            if required_role in caller_roles:
                return AuthDecision(allowed=True)

        return AuthDecision(
            allowed=False,
            reason=f"Caller role '{caller.role.value}' insufficient. "
                   f"Required: {tool.required_roles}",
        )

    def _check_tenant(self, caller: CallerIdentity, tool: ToolMeta) -> AuthDecision:
        """Verify tenant-level access."""
        if not self._tenant_policy.is_allowed(caller.tenant, tool.name):
            return AuthDecision(
                allowed=False,
                reason=f"Tenant '{caller.tenant}' denied access to '{tool.name}'.",
            )
        return AuthDecision(allowed=True)

    def _check_sensitive(self, caller: CallerIdentity, tool: ToolMeta) -> AuthDecision:
        """Check if sensitive tool requires confirmation."""
        if not tool.is_sensitive:
            return AuthDecision(allowed=True)

        if tool.name in caller.confirmed_tools:
            return AuthDecision(allowed=True)

        return AuthDecision(
            allowed=False,
            requires_confirmation=True,
            reason=f"Tool '{tool.name}' is sensitive and requires explicit confirmation.",
        )

    def _record_denial(self, caller: CallerIdentity, tool: ToolMeta, reason: str):
        self._denial_log.append({
            "timestamp": time.time(),
            "caller_id": caller.caller_id,
            "caller_role": caller.role.value,
            "tenant": caller.tenant,
            "tool_name": tool.name,
            "tool_version": tool.version,
            "reason": reason,
        })

    def confirm_sensitive_tool(self, caller: CallerIdentity, tool_name: str):
        """Record that a caller has confirmed use of a sensitive tool."""
        caller.confirmed_tools.add(tool_name)
