# W4 -> W5 Handover

## W4 Output Summary

### Code Modules

| Module | Path | Responsibility |
|--------|------|----------------|
| Tool Registry | `src/gateway/tool_registry.py` | Tool metadata, lifecycle (draft/available/deprecated), version management, catalog export |
| Error Codes | `src/gateway/errors.py` | Structured error codes (1xxx-5xxx), typed exceptions |
| Validator | `src/gateway/validator.py` | Schema validation, quota tracking (QPS/concurrency/daily) |
| Authorizer | `src/gateway/authorizer.py` | RBAC with hierarchy, tenant policy, sensitive tool confirmation |
| Circuit Breaker | `src/gateway/circuit_breaker.py` | Per-tool failure isolation, three-state model (closed/open/half-open) |
| Rate Limiter | `src/gateway/rate_limiter.py` | Token bucket per-caller, exponential backoff, degradation manager |
| Audit Logger | `src/gateway/audit_logger.py` | Structured audit trail, trace/session query, alert system |

### Documentation

| Document | Path |
|----------|------|
| Tool Lifecycle | `docs/tooling/tool-lifecycle.md` |
| Degradation Strategy | `docs/tooling/degrade-strategy.md` |
| Admission Checklist | `docs/tooling/tool-admission-checklist.md` |
| Authorization Model | `docs/security/tool-authz.md` |
| Audit Specification | `docs/security/audit-spec.md` |
| Error Codes Contract | `contracts/error-codes.yaml` |

### Test Coverage

| Test Suite | Path | Count |
|------------|------|-------|
| Registry Tests | `tests/gateway/test_tool_registry.py` | 16 |
| Validator Tests | `tests/gateway/test_validator.py` | 12 |
| Authorizer Tests | `tests/gateway/test_authorizer.py` | 14 |
| Circuit Breaker Tests | `tests/gateway/test_circuit_breaker.py` | 12 |
| Rate Limiter Tests | `tests/gateway/test_rate_limiter.py` | 12 |
| Audit Logger Tests | `tests/gateway/test_audit_logger.py` | 14 |
| Security Tests | `tests/security/test_tool_guardrails.py` | 15 |
| Integration Tests | `tests/integration/test_tool_resilience.py` | 12 |
| **Total** | | **107** |

## W5 Interface Requirements

### 1. Gateway Facade

W5 evaluation should use the gateway components in this order:

```python
from src.gateway.tool_registry import ToolRegistry
from src.gateway.validator import ToolValidator
from src.gateway.authorizer import ToolAuthorizer, CallerIdentity, Role
from src.gateway.circuit_breaker import CircuitBreaker
from src.gateway.rate_limiter import RateLimiter
from src.gateway.audit_logger import AuditLogger

# 1. Validate (schema + quota)
result = validator.validate(tool_name, params)
# 2. Authorize (role + tenant + sensitive)
decision = authorizer.authorize(caller, tool_meta)
# 3. Circuit check
allowed = circuit_breaker.allow_request(tool_name)
# 4. Rate limit
rate_result = rate_limiter.acquire(caller_id)
# 5. Execute tool
# 6. Record success/failure
# 7. Audit log
```

### 2. Evaluation Sampling Points

Recommended metrics for W5 evaluation:

| Metric | Source | Target |
|--------|--------|--------|
| Validation rejection rate | Validator | < 5% for well-formed agents |
| Auth denial rate | Authorizer denial_log | 0% for authorized callers |
| Circuit open frequency | CircuitBreaker stats | < 1% of tools |
| P99 validation latency | Audit Logger timestamps | < 5ms |
| Audit completeness | Audit entry_count vs call count | 100% |

### 3. Known Limitations

1. All storage is in-memory (process-scoped). Production needs persistence.
2. Quota tracking uses wall clock — no distributed coordination.
3. Rate limiter token refill uses `time.time()` — test with caution.
4. No tool execution engine yet — gateway validates but doesn't invoke.

### 4. Suggested W5 Focus

- Build tool execution engine that wires through the gateway
- Add end-to-end evaluation with real tool calls
- Measure gateway overhead (should be < 1ms per check)
- Evaluate LLM tool selection accuracy with catalog export
