"""Tests for audit logger."""

import pytest

from src.gateway.audit_logger import AuditEventType, AuditLogger


@pytest.fixture
def logger():
    return AuditLogger()


class TestCallLogging:
    def test_log_call_start(self, logger):
        event_id = logger.log_call_start(
            trace_id="t1", session_id="s1", caller_id="agent-1",
            tool_name="web_search", tool_version="1.0.0",
            params={"query": "hello"},
        )
        assert event_id
        assert logger.entry_count == 1
        entry = logger.entries[0]
        assert entry.event_type == AuditEventType.TOOL_CALL_START
        assert entry.params_hash  # non-empty hash

    def test_log_call_success(self, logger):
        logger.log_call_success(
            trace_id="t1", session_id="s1", caller_id="agent-1",
            tool_name="web_search", tool_version="1.0.0",
            result_summary="3 results", latency_ms=150.0,
        )
        entry = logger.entries[0]
        assert entry.event_type == AuditEventType.TOOL_CALL_SUCCESS
        assert entry.latency_ms == 150.0

    def test_log_call_failure(self, logger):
        logger.log_call_failure(
            trace_id="t1", session_id="s1", caller_id="agent-1",
            tool_name="web_search", tool_version="1.0.0",
            error="timeout", latency_ms=30000.0,
        )
        entry = logger.entries[0]
        assert entry.event_type == AuditEventType.TOOL_CALL_FAILURE
        assert entry.error == "timeout"


class TestEventLogging:
    def test_log_auth_denied(self, logger):
        logger.log_event(
            AuditEventType.AUTH_DENIED,
            trace_id="t1", session_id="s1", caller_id="agent-1",
            tool_name="admin_tool",
            error="insufficient role",
        )
        assert logger.entry_count == 1
        assert logger.entries[0].event_type == AuditEventType.AUTH_DENIED

    def test_log_circuit_opened(self, logger):
        entry = logger.log_event(
            AuditEventType.CIRCUIT_OPENED,
            trace_id="t1", session_id="s1", caller_id="system",
            tool_name="flaky_tool",
        )
        assert entry.tool_name == "flaky_tool"


class TestQuery:
    def test_query_by_trace(self, logger):
        logger.log_call_start("t1", "s1", "a1", "tool_a", "1.0", {})
        logger.log_call_start("t2", "s1", "a1", "tool_b", "1.0", {})
        logger.log_call_success("t1", "s1", "a1", "tool_a", "1.0", "ok", 100)
        results = logger.query_by_trace("t1")
        assert len(results) == 2
        assert all(e.trace_id == "t1" for e in results)

    def test_query_by_session(self, logger):
        logger.log_call_start("t1", "s1", "a1", "tool_a", "1.0", {})
        logger.log_call_start("t2", "s2", "a1", "tool_b", "1.0", {})
        results = logger.query_by_session("s1")
        assert len(results) == 1

    def test_query_by_tool(self, logger):
        logger.log_call_start("t1", "s1", "a1", "tool_a", "1.0", {})
        logger.log_call_success("t2", "s1", "a1", "tool_a", "1.0", "ok", 50)
        logger.log_call_start("t3", "s1", "a1", "tool_b", "1.0", {})

        all_a = logger.query_by_tool("tool_a")
        assert len(all_a) == 2

        success_a = logger.query_by_tool("tool_a", AuditEventType.TOOL_CALL_SUCCESS)
        assert len(success_a) == 1


class TestParamsHash:
    def test_same_params_same_hash(self, logger):
        logger.log_call_start("t1", "s1", "a1", "t", "1.0", {"a": 1, "b": 2})
        logger.log_call_start("t2", "s1", "a1", "t", "1.0", {"b": 2, "a": 1})
        assert logger.entries[0].params_hash == logger.entries[1].params_hash

    def test_different_params_different_hash(self, logger):
        logger.log_call_start("t1", "s1", "a1", "t", "1.0", {"a": 1})
        logger.log_call_start("t2", "s1", "a1", "t", "1.0", {"a": 2})
        assert logger.entries[0].params_hash != logger.entries[1].params_hash


class TestAlerts:
    def test_alert_on_critical_event(self, logger):
        alerts = []
        logger.register_alert_handler(lambda e: alerts.append(e))

        # AUTH_DENIED is a default alert event
        logger.log_event(AuditEventType.AUTH_DENIED, "t1", "s1", "a1", "tool")
        assert len(alerts) == 1

    def test_no_alert_on_normal_event(self, logger):
        alerts = []
        logger.register_alert_handler(lambda e: alerts.append(e))

        logger.log_call_success("t1", "s1", "a1", "tool", "1.0", "ok", 50)
        assert len(alerts) == 0

    def test_custom_alert_events(self, logger):
        alerts = []
        logger.register_alert_handler(lambda e: alerts.append(e))
        logger.set_alert_events({AuditEventType.RATE_LIMITED})

        logger.log_event(AuditEventType.AUTH_DENIED, "t1", "s1", "a1", "tool")
        assert len(alerts) == 0  # AUTH_DENIED no longer triggers

        logger.log_event(AuditEventType.RATE_LIMITED, "t2", "s1", "a1", "tool")
        assert len(alerts) == 1


class TestSerialization:
    def test_to_dict(self, logger):
        logger.log_call_start("t1", "s1", "a1", "tool", "1.0", {"q": "test"})
        d = logger.entries[0].to_dict()
        assert d["trace_id"] == "t1"
        assert d["event_type"] == "tool_call_start"
        assert isinstance(d["timestamp"], float)
