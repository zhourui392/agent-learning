"""Integration tests for tool resilience: circuit breaker, rate limiter, degradation.

Tests end-to-end behavior across multiple gateway components.
"""

import time

import pytest

from src.gateway.audit_logger import AuditEventType, AuditLogger
from src.gateway.authorizer import CallerIdentity, Role, ToolAuthorizer
from src.gateway.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
from src.gateway.rate_limiter import (
    DegradeManager,
    DegradeStrategy,
    RateLimitConfig,
    RateLimiter,
)
from src.gateway.tool_registry import ToolMeta, ToolRegistry, ToolStatus, QuotaConfig
from src.gateway.validator import ToolValidator


def _register_tool(registry, name="web_search", **kwargs):
    meta = ToolMeta(name=name, version="1.0.0", description=name,
                    status=ToolStatus.AVAILABLE, **kwargs)
    registry.register(meta)
    return meta


class TestCircuitBreakerResilience:
    """Test circuit breaker prevents cascading failures."""

    def test_circuit_opens_and_recovers(self):
        cb = CircuitBreaker(CircuitConfig(
            failure_threshold=3, recovery_timeout=0.1, success_threshold=1,
        ))
        # Trigger failures
        for _ in range(3):
            cb.record_failure("flaky_tool")
        assert cb.get_state("flaky_tool") == CircuitState.OPEN
        assert cb.allow_request("flaky_tool") is False

        # Wait for recovery
        time.sleep(0.15)
        assert cb.get_state("flaky_tool") == CircuitState.HALF_OPEN
        assert cb.allow_request("flaky_tool") is True

        # Successful probe closes circuit
        cb.record_success("flaky_tool")
        assert cb.get_state("flaky_tool") == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(CircuitConfig(
            failure_threshold=2, recovery_timeout=0.05, success_threshold=1,
        ))
        cb.record_failure("t")
        cb.record_failure("t")
        time.sleep(0.06)
        cb.get_state("t")  # trigger half-open
        cb.record_failure("t")
        assert cb.get_state("t") == CircuitState.OPEN

    def test_isolated_circuits(self):
        cb = CircuitBreaker(CircuitConfig(failure_threshold=2))
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN
        assert cb.get_state("tool_b") == CircuitState.CLOSED


class TestRateLimiterResilience:
    def test_burst_then_throttle(self):
        limiter = RateLimiter(RateLimitConfig(
            tokens_per_second=2.0, max_tokens=3,
        ))
        # Burst of 3 allowed
        for _ in range(3):
            assert limiter.acquire("c1").allowed
        # 4th should be denied
        assert not limiter.acquire("c1").allowed

    def test_refill_allows_more(self):
        limiter = RateLimiter(RateLimitConfig(
            tokens_per_second=100.0, max_tokens=2,
        ))
        limiter.acquire("c1")
        limiter.acquire("c1")
        time.sleep(0.05)  # Refill ~5 tokens
        assert limiter.acquire("c1").allowed


class TestDegradationFlow:
    def test_fallback_strategy(self):
        mgr = DegradeManager()
        mgr.register_strategy("search_v2", DegradeStrategy(
            fallback_tool="search_v1",
            message="v2 unavailable, using v1",
        ))

        # Simulate circuit open
        cb = CircuitBreaker(CircuitConfig(failure_threshold=2))
        cb.record_failure("search_v2")
        cb.record_failure("search_v2")

        if not cb.allow_request("search_v2"):
            strategy = mgr.get_strategy("search_v2")
            assert strategy is not None
            assert strategy.fallback_tool == "search_v1"

    def test_human_handoff_for_critical(self):
        mgr = DegradeManager()
        mgr.register_strategy("payment", DegradeStrategy(
            human_handoff=True,
            message="Payment service down, escalating",
        ))
        strategy = mgr.get_strategy("payment")
        assert strategy.human_handoff

    def test_no_strategy_returns_none(self):
        mgr = DegradeManager()
        assert mgr.get_strategy("unknown") is None


class TestEndToEndGateway:
    """Simulate a full request flow through all gateway components."""

    def test_happy_path(self):
        # Setup
        registry = ToolRegistry()
        _register_tool(registry, input_schema={"properties": {"q": {"type": "string"}}})
        validator = ToolValidator(registry)
        authorizer = ToolAuthorizer()
        cb = CircuitBreaker()
        limiter = RateLimiter()
        logger = AuditLogger()

        caller = CallerIdentity(caller_id="agent-1", role=Role.INTERNAL)
        tool = registry.get("web_search")

        # 1. Validate
        result = validator.validate("web_search", {"q": "test"})
        assert result.valid

        # 2. Authorize
        decision = authorizer.authorize(caller, tool)
        assert decision.allowed

        # 3. Circuit check
        assert cb.allow_request("web_search")

        # 4. Rate limit
        assert limiter.acquire("agent-1").allowed

        # 5. Audit
        logger.log_call_start("t1", "s1", "agent-1", "web_search", "1.0.0", {"q": "test"})
        cb.record_success("web_search")
        logger.log_call_success("t1", "s1", "agent-1", "web_search", "1.0.0", "ok", 100)

        assert logger.entry_count == 2

    def test_rejected_by_validation(self):
        registry = ToolRegistry()
        _register_tool(registry, input_schema={
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        })
        validator = ToolValidator(registry)
        logger = AuditLogger()

        result = validator.validate("web_search", {})
        assert not result.valid

        logger.log_event(AuditEventType.TOOL_CALL_REJECTED,
                         "t1", "s1", "agent-1", "web_search",
                         error=str(result.errors))
        assert logger.entry_count == 1

    def test_rejected_by_auth(self):
        registry = ToolRegistry()
        _register_tool(registry, required_roles=["admin"])
        authorizer = ToolAuthorizer()
        logger = AuditLogger()

        caller = CallerIdentity(caller_id="user1", role=Role.PUBLIC)
        tool = registry.get("web_search")
        decision = authorizer.authorize(caller, tool)
        assert not decision.allowed

        logger.log_event(AuditEventType.AUTH_DENIED,
                         "t1", "s1", "user1", "web_search",
                         error=decision.reason)
        assert logger.entry_count == 1

    def test_circuit_open_with_degradation(self):
        cb = CircuitBreaker(CircuitConfig(failure_threshold=2))
        mgr = DegradeManager()
        mgr.register_strategy("web_search", DegradeStrategy(
            fallback_tool="cached_search", message="Using cached results",
        ))
        logger = AuditLogger()

        cb.record_failure("web_search")
        cb.record_failure("web_search")

        if not cb.allow_request("web_search"):
            strategy = mgr.get_strategy("web_search")
            assert strategy.fallback_tool == "cached_search"
            logger.log_event(AuditEventType.DEGRADED,
                             "t1", "s1", "agent-1", "web_search",
                             metadata={"fallback": strategy.fallback_tool})

        assert logger.entry_count == 1
        assert logger.entries[0].metadata["fallback"] == "cached_search"
