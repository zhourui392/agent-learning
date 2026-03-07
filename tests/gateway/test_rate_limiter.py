"""Tests for rate limiter and degrade manager."""

import pytest

from src.gateway.rate_limiter import (
    DegradeManager,
    DegradeStrategy,
    RateLimitConfig,
    RateLimiter,
)


@pytest.fixture
def limiter():
    return RateLimiter(RateLimitConfig(
        tokens_per_second=10.0,
        max_tokens=5,
        backoff_base=1.0,
        backoff_multiplier=2.0,
        backoff_max=16.0,
    ))


class TestTokenBucket:
    def test_allows_within_capacity(self, limiter):
        result = limiter.acquire("caller_1")
        assert result.allowed
        assert result.remaining_tokens == 4

    def test_denies_when_empty(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        result = limiter.acquire("caller_1")
        assert not result.allowed
        assert result.retry_after > 0

    def test_check_does_not_consume(self, limiter):
        result1 = limiter.check("caller_1")
        result2 = limiter.check("caller_1")
        assert result1.remaining_tokens == result2.remaining_tokens

    def test_callers_isolated(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        result = limiter.acquire("caller_2")
        assert result.allowed


class TestBackoff:
    def test_exponential_backoff(self, limiter):
        # Drain bucket
        for _ in range(5):
            limiter.acquire("caller_1")

        r1 = limiter.acquire("caller_1")
        assert r1.retry_after == 1.0  # base * 2^0

        r2 = limiter.acquire("caller_1")
        assert r2.retry_after == 2.0  # base * 2^1

        r3 = limiter.acquire("caller_1")
        assert r3.retry_after == 4.0  # base * 2^2

    def test_backoff_capped(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        # Trigger many rejections
        for _ in range(10):
            limiter.acquire("caller_1")
        result = limiter.acquire("caller_1")
        assert result.retry_after <= 16.0

    def test_backoff_resets_on_success(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        limiter.acquire("caller_1")  # rejection 1
        limiter.reset("caller_1")
        result = limiter.acquire("caller_1")
        assert result.allowed


class TestReset:
    def test_reset_specific_caller(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        limiter.reset("caller_1")
        result = limiter.acquire("caller_1")
        assert result.allowed

    def test_reset_all(self, limiter):
        for _ in range(5):
            limiter.acquire("caller_1")
        for _ in range(5):
            limiter.acquire("caller_2")
        limiter.reset()
        assert limiter.acquire("caller_1").allowed
        assert limiter.acquire("caller_2").allowed


class TestDegradeManager:
    def test_register_and_get_strategy(self):
        mgr = DegradeManager()
        strategy = DegradeStrategy(
            fallback_tool="search_v1",
            message="Using fallback search",
        )
        mgr.register_strategy("search_v2", strategy)
        assert mgr.should_degrade("search_v2")
        result = mgr.get_strategy("search_v2")
        assert result.fallback_tool == "search_v1"

    def test_no_strategy_returns_none(self):
        mgr = DegradeManager()
        assert mgr.get_strategy("unknown") is None
        assert not mgr.should_degrade("unknown")

    def test_human_handoff_strategy(self):
        mgr = DegradeManager()
        mgr.register_strategy("critical_op", DegradeStrategy(
            human_handoff=True,
            message="Requires human intervention",
        ))
        strategy = mgr.get_strategy("critical_op")
        assert strategy.human_handoff
