"""Security tests for tool gateway guardrails.

Covers: malicious input, privilege escalation, parameter pollution.
"""

import pytest

from src.gateway.authorizer import CallerIdentity, Role, TenantPolicy, ToolAuthorizer
from src.gateway.tool_registry import ToolMeta, ToolRegistry, ToolStatus, QuotaConfig
from src.gateway.validator import ToolValidator, QuotaTracker


def _available_tool(name="tool", **kwargs):
    return ToolMeta(name=name, version="1.0.0", description=name,
                    status=ToolStatus.AVAILABLE, **kwargs)


class TestMaliciousInput:
    """Test that malicious/adversarial inputs are safely handled."""

    @pytest.fixture
    def validator(self):
        r = ToolRegistry()
        r.register(_available_tool(
            name="search",
            input_schema={
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ))
        return ToolValidator(r)

    def test_sql_injection_in_params(self, validator):
        """SQL injection strings should pass schema validation (not our layer) but not crash."""
        result = validator.validate("search", {"query": "'; DROP TABLE users; --"})
        assert result.valid  # String type is correct, content filtering is tool's job

    def test_script_injection_in_params(self, validator):
        result = validator.validate("search", {"query": "<script>alert(1)</script>"})
        assert result.valid  # Schema validation only checks types

    def test_extremely_long_input(self, validator):
        result = validator.validate("search", {"query": "x" * 1_000_000})
        assert result.valid  # Schema doesn't limit length by default

    def test_null_bytes_in_params(self, validator):
        result = validator.validate("search", {"query": "hello\x00world"})
        assert result.valid

    def test_nested_object_injection(self, validator):
        """Extra unexpected fields should not cause errors."""
        result = validator.validate("search", {
            "query": "test",
            "__proto__": {"admin": True},
            "constructor": "evil",
        })
        assert result.valid  # Extra fields are ignored

    def test_empty_params(self, validator):
        result = validator.validate("search", {})
        assert not result.valid  # Missing required field

    def test_none_param_value(self, validator):
        result = validator.validate("search", {"query": None})
        assert not result.valid  # Expected string, got null

    def test_nonexistent_tool_name(self, validator):
        result = validator.validate("../../etc/passwd", {})
        assert not result.valid


class TestPrivilegeEscalation:
    """Test that role boundaries cannot be bypassed."""

    @pytest.fixture
    def auth(self):
        policy = TenantPolicy()
        policy.set_deny_list("restricted", ["admin_tool"])
        return ToolAuthorizer(tenant_policy=policy)

    def test_public_cannot_access_admin(self, auth):
        caller = CallerIdentity(caller_id="user1", role=Role.PUBLIC)
        tool = _available_tool(name="admin_tool", required_roles=["admin"])
        decision = auth.authorize(caller, tool)
        assert not decision.allowed

    def test_internal_cannot_access_admin(self, auth):
        caller = CallerIdentity(caller_id="user1", role=Role.INTERNAL)
        tool = _available_tool(name="admin_tool", required_roles=["admin"])
        decision = auth.authorize(caller, tool)
        assert not decision.allowed

    def test_tenant_deny_overrides_admin_role(self, auth):
        """Even admin role is denied if tenant policy blocks the tool."""
        caller = CallerIdentity(caller_id="admin1", role=Role.ADMIN, tenant="restricted")
        tool = _available_tool(name="admin_tool", required_roles=["public"])
        decision = auth.authorize(caller, tool)
        assert not decision.allowed

    def test_sensitive_tool_requires_confirmation(self, auth):
        caller = CallerIdentity(caller_id="admin1", role=Role.ADMIN)
        tool = _available_tool(name="delete_db", is_sensitive=True)
        decision = auth.authorize(caller, tool)
        assert not decision.allowed
        assert decision.requires_confirmation

    def test_all_denials_audited(self, auth):
        caller = CallerIdentity(caller_id="attacker", role=Role.PUBLIC)
        tool = _available_tool(name="admin_tool", required_roles=["admin"])
        for _ in range(5):
            auth.authorize(caller, tool)
        assert len(auth.denial_log) == 5


class TestParameterPollution:
    """Test that duplicate/conflicting parameters are handled safely."""

    def test_type_coercion_attack(self):
        """Passing wrong type should be caught."""
        r = ToolRegistry()
        r.register(_available_tool(
            name="calc",
            input_schema={
                "properties": {"amount": {"type": "integer"}},
                "required": ["amount"],
            },
        ))
        v = ToolValidator(r)
        result = v.validate("calc", {"amount": "999999999"})
        assert not result.valid

    def test_boolean_as_string(self):
        r = ToolRegistry()
        r.register(_available_tool(
            name="toggle",
            input_schema={"properties": {"enabled": {"type": "boolean"}}},
        ))
        v = ToolValidator(r)
        result = v.validate("toggle", {"enabled": "true"})
        assert not result.valid
