# Tool Authorization Model

## Overview

The tool authorization system implements a **default-deny** policy with three layers of checks evaluated in order. A request must pass all layers to be authorized.

## Authorization Layers

### 1. Role-Based Access Control (RBAC)

Hierarchical roles with automatic inheritance:

```
ADMIN  -> {PUBLIC, INTERNAL, ADMIN}
INTERNAL -> {PUBLIC, INTERNAL}
PUBLIC   -> {PUBLIC}
```

Each tool declares `required_roles`. The caller's role must include at least one of the required roles (via hierarchy).

**Example:** A tool with `required_roles=["internal"]` is accessible to INTERNAL and ADMIN callers, but not PUBLIC.

### 2. Tenant-Level Policy

Per-tenant allow/deny lists for fine-grained control:

- **Deny list** takes precedence over allow list
- **Allow list** restricts to only listed tools (empty = allow all)
- **No policy** = allow all tools

```python
policy = TenantPolicy()
policy.set_deny_list("tenant_a", ["dangerous_tool"])
policy.set_allow_list("tenant_b", ["safe_tool_1", "safe_tool_2"])
```

### 3. Sensitive Tool Confirmation

Tools marked `is_sensitive=True` require explicit caller confirmation before invocation.

- First call returns `AuthDecision(allowed=False, requires_confirmation=True)`
- Agent/UI must prompt user and call `confirm_sensitive_tool(caller, tool_name)`
- Subsequent calls within the same session are allowed

**Use cases:** file deletion, database writes, external API calls with side effects.

## Caller Identity

```python
CallerIdentity(
    caller_id="agent-1",     # Unique identifier
    role=Role.INTERNAL,       # Determines access level
    tenant="default",         # Tenant isolation
    confirmed_tools=set(),    # Runtime confirmation state
)
```

## Denial Audit

All denied attempts are logged with:
- Timestamp, caller ID, role, tenant
- Tool name, version
- Denial reason

Access via `authorizer.denial_log`.

## Minimum Privilege Principle

- New tools default to `required_roles=["public"]` — tighten as needed
- Sensitive operations should use `is_sensitive=True` + `required_roles=["admin"]`
- Tenant policies should start restrictive (allow list) and expand
