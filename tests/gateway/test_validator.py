"""Tests for pre-invocation validator."""

import pytest

from src.gateway.errors import *
from src.gateway.tool_registry import QuotaConfig, ToolMeta, ToolRegistry, ToolStatus
from src.gateway.validator import QuotaTracker, ToolValidator, ValidationResult


@pytest.fixture
def registry():
    r = ToolRegistry()
    meta = ToolMeta(
        name="web_search",
        version="1.0.0",
        description="Search the web",
        status=ToolStatus.AVAILABLE,
        input_schema={
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
        quota=QuotaConfig(qps=5, max_concurrent=2, daily_limit=100),
    )
    r.register(meta)
    return r


@pytest.fixture
def validator(registry):
    return ToolValidator(registry)


class TestToolExistence:
    def test_nonexistent_tool(self, validator):
        result = validator.validate("nonexistent", {})
        assert not result.valid
        assert result.errors[0]["code"] == INVALID_TOOL_NAME.code

    def test_draft_tool_rejected(self, registry):
        registry.register(ToolMeta(name="draft_tool", version="1.0.0",
                                   description="draft", status=ToolStatus.DRAFT))
        v = ToolValidator(registry)
        result = v.validate("draft_tool", {})
        assert not result.valid
        assert result.errors[0]["code"] == TOOL_NOT_AVAILABLE.code


class TestSchemaValidation:
    def test_valid_params(self, validator):
        result = validator.validate("web_search", {"query": "hello"})
        assert result.valid

    def test_missing_required_field(self, validator):
        result = validator.validate("web_search", {})
        assert not result.valid
        assert any(e["code"] == MISSING_REQUIRED_FIELD.code for e in result.errors)

    def test_wrong_type(self, validator):
        result = validator.validate("web_search", {"query": "hello", "limit": "not_int"})
        assert not result.valid
        assert any(e["code"] == INVALID_FIELD_TYPE.code for e in result.errors)

    def test_number_accepts_integer(self, registry):
        registry.register(ToolMeta(
            name="calc", version="1.0.0", description="calc",
            status=ToolStatus.AVAILABLE,
            input_schema={"value": {"type": "number"}},
        ))
        v = ToolValidator(registry)
        result = v.validate("calc", {"value": 42})
        assert result.valid

    def test_no_schema_passes(self, registry):
        registry.register(ToolMeta(
            name="no_schema", version="1.0.0", description="no schema",
            status=ToolStatus.AVAILABLE,
        ))
        v = ToolValidator(registry)
        result = v.validate("no_schema", {"anything": "goes"})
        assert result.valid


class TestQuotaValidation:
    def test_qps_exceeded(self, registry):
        tracker = QuotaTracker()
        v = ToolValidator(registry, quota_tracker=tracker)
        # Simulate 5 calls (at QPS limit)
        for _ in range(5):
            tracker.record_call_start("web_search")
        result = v.validate("web_search", {"query": "test"})
        assert not result.valid
        assert any(e["code"] == QPS_EXCEEDED.code for e in result.errors)

    def test_concurrency_exceeded(self, registry):
        tracker = QuotaTracker()
        v = ToolValidator(registry, quota_tracker=tracker)
        # Simulate 2 concurrent calls (at limit)
        tracker.record_call_start("web_search")
        tracker.record_call_start("web_search")
        result = v.validate("web_search", {"query": "test"})
        assert not result.valid
        assert any(e["code"] == CONCURRENCY_EXCEEDED.code for e in result.errors)

    def test_concurrency_released(self, registry):
        tracker = QuotaTracker()
        v = ToolValidator(registry, quota_tracker=tracker)
        tracker.record_call_start("web_search")
        tracker.record_call_start("web_search")
        tracker.record_call_end("web_search")
        # Now only 1 concurrent, limit is 2
        result = v.validate("web_search", {"query": "test"})
        # Should still fail QPS (2 calls in window) but concurrency is fine
        concurrency_errors = [e for e in result.errors if e["code"] == CONCURRENCY_EXCEEDED.code]
        assert len(concurrency_errors) == 0

    def test_quota_reset(self, registry):
        tracker = QuotaTracker()
        v = ToolValidator(registry, quota_tracker=tracker)
        for _ in range(5):
            tracker.record_call_start("web_search")
        tracker.reset("web_search")
        result = v.validate("web_search", {"query": "test"})
        assert result.valid


class TestMultipleErrors:
    def test_accumulates_errors(self, validator):
        """Missing required field + wrong type should both be reported."""
        result = validator.validate("web_search", {"limit": "bad"})
        assert not result.valid
        codes = {e["code"] for e in result.errors}
        assert MISSING_REQUIRED_FIELD.code in codes
        assert INVALID_FIELD_TYPE.code in codes
