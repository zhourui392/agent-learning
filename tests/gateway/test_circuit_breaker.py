"""Tests for circuit breaker."""

import time
from unittest.mock import patch

import pytest

from src.gateway.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState


@pytest.fixture
def cb():
    return CircuitBreaker(CircuitConfig(
        failure_threshold=3,
        recovery_timeout=5.0,
        success_threshold=2,
    ))


class TestClosedState:
    def test_starts_closed(self, cb):
        assert cb.get_state("tool_a") == CircuitState.CLOSED

    def test_allows_requests(self, cb):
        assert cb.allow_request("tool_a") is True

    def test_stays_closed_under_threshold(self, cb):
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.CLOSED

    def test_success_resets_failure_count(self, cb):
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        cb.record_success("tool_a")
        cb.record_failure("tool_a")
        cb.record_failure("tool_a")
        # Only 2 consecutive failures, not 3
        assert cb.get_state("tool_a") == CircuitState.CLOSED


class TestOpenState:
    def test_opens_after_threshold(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN

    def test_rejects_requests_when_open(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        assert cb.allow_request("tool_a") is False

    def test_tracks_rejections(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        cb.allow_request("tool_a")
        stats = cb.get_stats("tool_a")
        assert stats.total_rejections == 1


class TestHalfOpenState:
    def test_transitions_after_timeout(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN

        # Simulate time passing
        cb._circuits["tool_a"].last_state_change = time.time() - 6.0
        assert cb.get_state("tool_a") == CircuitState.HALF_OPEN

    def test_closes_after_success_threshold(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        cb._circuits["tool_a"].last_state_change = time.time() - 6.0
        cb.get_state("tool_a")  # trigger transition

        cb.record_success("tool_a")
        assert cb.get_state("tool_a") == CircuitState.HALF_OPEN
        cb.record_success("tool_a")
        assert cb.get_state("tool_a") == CircuitState.CLOSED

    def test_reopens_on_failure(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        cb._circuits["tool_a"].last_state_change = time.time() - 6.0
        cb.get_state("tool_a")  # trigger half-open

        cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN


class TestManualReset:
    def test_reset_closes_circuit(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN
        cb.reset("tool_a")
        assert cb.get_state("tool_a") == CircuitState.CLOSED


class TestIsolation:
    def test_tools_are_isolated(self, cb):
        for _ in range(3):
            cb.record_failure("tool_a")
        assert cb.get_state("tool_a") == CircuitState.OPEN
        assert cb.get_state("tool_b") == CircuitState.CLOSED
