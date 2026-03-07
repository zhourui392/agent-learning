"""Tests for authorization module."""

import pytest

from src.gateway.authorizer import (
    AuthDecision,
    CallerIdentity,
    Role,
    TenantPolicy,
    ToolAuthorizer,
)
from src.gateway.tool_registry import ToolMeta, ToolStatus


def _tool(name="web_search", required_roles=None, is_sensitive=False):
    return ToolMeta(
        name=name, version="1.0.0", description=name,
        status=ToolStatus.AVAILABLE,
        required_roles=required_roles or ["public"],
        is_sensitive=is_sensitive,
    )


def _caller(role=Role.PUBLIC, tenant="default", caller_id="agent-1"):
    return CallerIdentity(caller_id=caller_id, role=role, tenant=tenant)


class TestRoleBasedAccess:
    def test_public_accesses_public_tool(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(Role.PUBLIC), _tool(required_roles=["public"]))
        assert decision.allowed

    def test_public_denied_internal_tool(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(Role.PUBLIC), _tool(required_roles=["internal"]))
        assert not decision.allowed

    def test_internal_accesses_public_tool(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(Role.INTERNAL), _tool(required_roles=["public"]))
        assert decision.allowed

    def test_admin_accesses_all(self):
        auth = ToolAuthorizer()
        for role_req in ["public", "internal", "admin"]:
            decision = auth.authorize(_caller(Role.ADMIN), _tool(required_roles=[role_req]))
            assert decision.allowed

    def test_internal_denied_admin_tool(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(Role.INTERNAL), _tool(required_roles=["admin"]))
        assert not decision.allowed


class TestTenantPolicy:
    def test_deny_list(self):
        policy = TenantPolicy()
        policy.set_deny_list("tenant_a", ["dangerous_tool"])
        auth = ToolAuthorizer(tenant_policy=policy)
        decision = auth.authorize(
            _caller(Role.ADMIN, tenant="tenant_a"),
            _tool(name="dangerous_tool"),
        )
        assert not decision.allowed

    def test_allow_list(self):
        policy = TenantPolicy()
        policy.set_allow_list("tenant_b", ["safe_tool"])
        auth = ToolAuthorizer(tenant_policy=policy)

        # Allowed tool
        decision = auth.authorize(
            _caller(Role.PUBLIC, tenant="tenant_b"),
            _tool(name="safe_tool"),
        )
        assert decision.allowed

        # Not in allow list
        decision = auth.authorize(
            _caller(Role.PUBLIC, tenant="tenant_b"),
            _tool(name="other_tool"),
        )
        assert not decision.allowed

    def test_deny_overrides_allow(self):
        policy = TenantPolicy()
        policy.set_allow_list("tenant_c", ["tool_x"])
        policy.set_deny_list("tenant_c", ["tool_x"])
        auth = ToolAuthorizer(tenant_policy=policy)
        decision = auth.authorize(
            _caller(Role.ADMIN, tenant="tenant_c"),
            _tool(name="tool_x"),
        )
        assert not decision.allowed

    def test_no_policy_allows_all(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(tenant="unknown"), _tool())
        assert decision.allowed


class TestSensitiveToolConfirmation:
    def test_sensitive_requires_confirmation(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(), _tool(is_sensitive=True))
        assert not decision.allowed
        assert decision.requires_confirmation

    def test_confirmed_sensitive_allowed(self):
        auth = ToolAuthorizer()
        caller = _caller()
        tool = _tool(name="delete_file", is_sensitive=True)
        auth.confirm_sensitive_tool(caller, "delete_file")
        decision = auth.authorize(caller, tool)
        assert decision.allowed

    def test_non_sensitive_no_confirmation(self):
        auth = ToolAuthorizer()
        decision = auth.authorize(_caller(), _tool(is_sensitive=False))
        assert decision.allowed
        assert not decision.requires_confirmation


class TestDenialAudit:
    def test_denial_logged(self):
        auth = ToolAuthorizer()
        auth.authorize(_caller(Role.PUBLIC), _tool(required_roles=["admin"]))
        assert len(auth.denial_log) == 1
        entry = auth.denial_log[0]
        assert entry["caller_role"] == "public"
        assert entry["tool_name"] == "web_search"

    def test_allowed_not_logged(self):
        auth = ToolAuthorizer()
        auth.authorize(_caller(Role.ADMIN), _tool(required_roles=["public"]))
        assert len(auth.denial_log) == 0
