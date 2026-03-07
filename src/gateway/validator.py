"""Pre-invocation validator - schema check, quota check, tool availability.

All checks run BEFORE a tool is actually invoked, blocking invalid requests early.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.gateway.errors import (
    CONCURRENCY_EXCEEDED,
    DAILY_QUOTA_EXCEEDED,
    INVALID_FIELD_TYPE,
    INVALID_TOOL_NAME,
    MISSING_REQUIRED_FIELD,
    QPS_EXCEEDED,
    SCHEMA_VIOLATION,
    TOOL_NOT_AVAILABLE,
    QuotaError,
    ValidationError,
)
from src.gateway.tool_registry import ToolMeta, ToolRegistry, ToolStatus

# Python type name -> JSON Schema type mapping
_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "NoneType": "null",
}


@dataclass
class ValidationResult:
    """Result of a pre-invocation validation."""
    valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def add_error(self, error_code, **kwargs):
        self.valid = False
        self.errors.append({
            "code": error_code.code,
            "category": error_code.category.value,
            "message": error_code.format(**kwargs),
        })


class QuotaTracker:
    """Tracks per-tool quota usage: QPS, concurrency, and daily limits."""

    def __init__(self):
        # {tool_name: [timestamps]} for QPS sliding window
        self._call_timestamps: Dict[str, List[float]] = defaultdict(list)
        # {tool_name: count} for concurrent calls
        self._concurrent: Dict[str, int] = defaultdict(int)
        # {(tool_name, date_str): count} for daily quota
        self._daily_counts: Dict[tuple, int] = defaultdict(int)

    def check_qps(self, tool_name: str, limit: int) -> bool:
        """Check if QPS limit allows a new call. Uses 1-second sliding window."""
        now = time.time()
        timestamps = self._call_timestamps[tool_name]
        # Remove entries older than 1 second
        self._call_timestamps[tool_name] = [t for t in timestamps if now - t < 1.0]
        return len(self._call_timestamps[tool_name]) < limit

    def check_concurrency(self, tool_name: str, limit: int) -> bool:
        return self._concurrent[tool_name] < limit

    def check_daily(self, tool_name: str, limit: int) -> bool:
        key = (tool_name, time.strftime("%Y-%m-%d"))
        return self._daily_counts[key] < limit

    def record_call_start(self, tool_name: str):
        """Record a call starting (for QPS and concurrency tracking)."""
        self._call_timestamps[tool_name].append(time.time())
        self._concurrent[tool_name] += 1
        key = (tool_name, time.strftime("%Y-%m-%d"))
        self._daily_counts[key] += 1

    def record_call_end(self, tool_name: str):
        """Record a call finishing (for concurrency tracking)."""
        self._concurrent[tool_name] = max(0, self._concurrent[tool_name] - 1)

    def reset(self, tool_name: Optional[str] = None):
        """Reset all or per-tool quota counters."""
        if tool_name:
            self._call_timestamps.pop(tool_name, None)
            self._concurrent.pop(tool_name, None)
            keys_to_remove = [k for k in self._daily_counts if k[0] == tool_name]
            for k in keys_to_remove:
                del self._daily_counts[k]
        else:
            self._call_timestamps.clear()
            self._concurrent.clear()
            self._daily_counts.clear()


class ToolValidator:
    """Pre-invocation validator that checks tool availability, schema, and quota."""

    def __init__(self, registry: ToolRegistry, quota_tracker: Optional[QuotaTracker] = None):
        self._registry = registry
        self._quota = quota_tracker or QuotaTracker()

    @property
    def quota_tracker(self) -> QuotaTracker:
        return self._quota

    def validate(self, tool_name: str, params: Dict[str, Any]) -> ValidationResult:
        """Run all pre-invocation checks. Returns ValidationResult."""
        result = ValidationResult(valid=True)

        # 1. Tool existence
        meta = self._registry.get(tool_name)
        if not meta:
            result.add_error(INVALID_TOOL_NAME, tool_name=tool_name)
            return result  # No point continuing

        # 2. Tool availability
        if meta.status != ToolStatus.AVAILABLE:
            result.add_error(TOOL_NOT_AVAILABLE, tool_name=tool_name, status=meta.status.value)
            return result

        # 3. Schema validation
        self._validate_schema(meta, params, result)

        # 4. Quota checks
        self._validate_quota(meta, result)

        return result

    def _validate_schema(self, meta: ToolMeta, params: Dict[str, Any],
                         result: ValidationResult):
        """Validate params against the tool's input_schema."""
        schema = meta.input_schema
        if not schema:
            return  # No schema defined, skip validation

        # Check required fields
        required = schema.get("required", [])
        properties = schema.get("properties", schema)

        # If schema is a flat dict of {field: {type: ...}}, treat all keys as properties
        if "properties" not in schema and "required" not in schema:
            properties = schema
            required = []

        for field_name in required:
            if field_name not in params:
                result.add_error(MISSING_REQUIRED_FIELD, field_name=field_name)

        # Check types for provided fields
        for field_name, field_spec in properties.items():
            if field_name in ("required", "properties"):
                continue
            if field_name not in params:
                continue

            expected_type = field_spec.get("type") if isinstance(field_spec, dict) else None
            if not expected_type:
                continue

            actual_value = params[field_name]
            actual_type = _TYPE_MAP.get(type(actual_value).__name__, type(actual_value).__name__)

            # Allow integer where number is expected
            if expected_type == "number" and actual_type == "integer":
                continue

            if actual_type != expected_type:
                result.add_error(INVALID_FIELD_TYPE,
                                 field_name=field_name,
                                 expected=expected_type,
                                 actual=actual_type)

    def _validate_quota(self, meta: ToolMeta, result: ValidationResult):
        """Check QPS, concurrency, and daily quota."""
        quota = meta.quota

        if not self._quota.check_qps(meta.name, quota.qps):
            result.add_error(QPS_EXCEEDED, tool_name=meta.name, limit=quota.qps)

        if not self._quota.check_concurrency(meta.name, quota.max_concurrent):
            result.add_error(CONCURRENCY_EXCEEDED, tool_name=meta.name, limit=quota.max_concurrent)

        if not self._quota.check_daily(meta.name, quota.daily_limit):
            result.add_error(DAILY_QUOTA_EXCEEDED, tool_name=meta.name, limit=quota.daily_limit)
