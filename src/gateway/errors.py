"""Structured error codes and exceptions for tool gateway."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(Enum):
    VALIDATION = "validation"
    QUOTA = "quota"
    AUTH = "auth"
    RUNTIME = "runtime"
    DEGRADATION = "degradation"


@dataclass(frozen=True)
class ErrorCode:
    code: int
    category: ErrorCategory
    message_template: str

    def format(self, **kwargs) -> str:
        return self.message_template.format(**kwargs)


# --- Error code registry ---

INVALID_TOOL_NAME = ErrorCode(1001, ErrorCategory.VALIDATION,
                              "Tool '{tool_name}' is not registered.")
TOOL_NOT_AVAILABLE = ErrorCode(1002, ErrorCategory.VALIDATION,
                               "Tool '{tool_name}' is not in AVAILABLE state (current: {status}).")
SCHEMA_VIOLATION = ErrorCode(1003, ErrorCategory.VALIDATION,
                             "Input validation failed: {details}")
MISSING_REQUIRED_FIELD = ErrorCode(1004, ErrorCategory.VALIDATION,
                                   "Missing required field: {field_name}")
INVALID_FIELD_TYPE = ErrorCode(1005, ErrorCategory.VALIDATION,
                               "Field '{field_name}' expected type '{expected}', got '{actual}'.")

QPS_EXCEEDED = ErrorCode(2001, ErrorCategory.QUOTA,
                         "QPS limit exceeded for tool '{tool_name}' (limit: {limit}/s).")
CONCURRENCY_EXCEEDED = ErrorCode(2002, ErrorCategory.QUOTA,
                                 "Concurrency limit exceeded for tool '{tool_name}' (limit: {limit}).")
DAILY_QUOTA_EXCEEDED = ErrorCode(2003, ErrorCategory.QUOTA,
                                 "Daily quota exceeded for tool '{tool_name}' (limit: {limit}/day).")

UNAUTHORIZED = ErrorCode(3001, ErrorCategory.AUTH,
                         "Caller '{caller}' lacks required role for tool '{tool_name}'.")
SENSITIVE_TOOL_UNCONFIRMED = ErrorCode(3002, ErrorCategory.AUTH,
                                       "Tool '{tool_name}' is sensitive and requires explicit confirmation.")
TENANT_DENIED = ErrorCode(3003, ErrorCategory.AUTH,
                          "Tenant '{tenant}' is not authorized to use tool '{tool_name}'.")

TOOL_TIMEOUT = ErrorCode(4001, ErrorCategory.RUNTIME,
                         "Tool '{tool_name}' timed out after {timeout}s.")
CIRCUIT_OPEN = ErrorCode(4002, ErrorCategory.RUNTIME,
                         "Circuit breaker open for tool '{tool_name}'. Try again later.")
TOOL_EXECUTION_ERROR = ErrorCode(4003, ErrorCategory.RUNTIME,
                                 "Tool '{tool_name}' execution failed: {details}")
RATE_LIMITED = ErrorCode(4004, ErrorCategory.RUNTIME,
                         "Rate limited for caller '{caller}'. Retry after {retry_after}s.")

DEGRADED_RESPONSE = ErrorCode(5001, ErrorCategory.DEGRADATION,
                              "Tool '{tool_name}' returned a degraded response: {strategy}.")
FALLBACK_USED = ErrorCode(5002, ErrorCategory.DEGRADATION,
                          "Fallback tool '{fallback}' used instead of '{tool_name}'.")


class ToolGatewayError(Exception):
    """Base exception for tool gateway errors."""

    def __init__(self, error_code: ErrorCode, **kwargs):
        self.error_code = error_code
        self.params = kwargs
        self.message = error_code.format(**kwargs)
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.error_code.code,
            "category": self.error_code.category.value,
            "message": self.message,
            "params": self.params,
        }


class ValidationError(ToolGatewayError):
    """Raised when input validation fails."""
    pass


class QuotaError(ToolGatewayError):
    """Raised when quota limits are exceeded."""
    pass


class AuthError(ToolGatewayError):
    """Raised when authorization fails."""
    pass


class RuntimeToolError(ToolGatewayError):
    """Raised on tool execution failures."""
    pass
