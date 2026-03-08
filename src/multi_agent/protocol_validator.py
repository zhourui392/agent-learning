"""Validation for W7 multi-agent messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


SUPPORTED_ROLES = {"planner", "executor", "auditor", "coordinator", "human"}
SUPPORTED_MESSAGE_TYPES = {
    "task_request",
    "task_result",
    "audit_review",
    "conflict_notice",
    "memory_update",
}
SUPPORTED_STATUSES = {"pending", "running", "completed", "failed", "needs_human"}
SUPPORTED_VERSION_PREFIXES = ("1.",)


@dataclass
class ProtocolValidationResult:
    """Validation outcome for one message payload."""

    valid: bool
    errors: List[str] = field(default_factory=list)


class ProtocolValidator:
    """Validate messages against the W7 protocol contract."""

    def validate_message(self, message: Dict[str, Any]) -> ProtocolValidationResult:
        """Validate one multi-agent message dict."""

        errors: List[str] = []
        self._validate_top_level(message, errors)
        if errors:
            return ProtocolValidationResult(valid=False, errors=errors)

        header = message["header"]
        meta = message["meta"]
        self._validate_header(header, errors)
        self._validate_meta(meta, errors)
        self._validate_payload(message["payload"], header, errors)
        return ProtocolValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_top_level(self, message: Dict[str, Any], errors: List[str]) -> None:
        required_fields = ["version", "header", "payload", "meta"]
        for field_name in required_fields:
            if field_name not in message:
                errors.append(f"missing top-level field: {field_name}")
        version = message.get("version")
        if not isinstance(version, str):
            errors.append("version must be string")
            return
        if not version.startswith(SUPPORTED_VERSION_PREFIXES):
            errors.append(f"unsupported version: {version}")

    def _validate_header(self, header: Dict[str, Any], errors: List[str]) -> None:
        required_fields = ["message_id", "message_type", "sender_role", "receiver_role", "task_id"]
        for field_name in required_fields:
            if field_name not in header:
                errors.append(f"missing header field: {field_name}")
        sender_role = header.get("sender_role")
        receiver_role = header.get("receiver_role")
        message_type = header.get("message_type")
        if sender_role not in SUPPORTED_ROLES:
            errors.append(f"unsupported sender_role: {sender_role}")
        if receiver_role not in SUPPORTED_ROLES:
            errors.append(f"unsupported receiver_role: {receiver_role}")
        if message_type not in SUPPORTED_MESSAGE_TYPES:
            errors.append(f"unsupported message_type: {message_type}")

    def _validate_meta(self, meta: Dict[str, Any], errors: List[str]) -> None:
        required_fields = ["trace_id", "session_id", "status", "priority"]
        for field_name in required_fields:
            if field_name not in meta:
                errors.append(f"missing meta field: {field_name}")
        if meta.get("status") not in SUPPORTED_STATUSES:
            errors.append(f"unsupported status: {meta.get('status')}")
        priority = meta.get("priority")
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            errors.append("priority must be integer in range 1..5")
        conflict_fields = meta.get("conflict_fields", [])
        if not isinstance(conflict_fields, list):
            errors.append("conflict_fields must be list")

    def _validate_payload(
        self,
        payload: Dict[str, Any],
        header: Dict[str, Any],
        errors: List[str],
    ) -> None:
        if not isinstance(payload, dict):
            errors.append("payload must be object")
            return
        message_type = header.get("message_type")
        if message_type == "task_request" and "instruction" not in payload:
            errors.append("task_request requires payload.instruction")
        if message_type == "task_result" and "result" not in payload:
            errors.append("task_result requires payload.result")
        if message_type == "audit_review" and "review" not in payload:
            errors.append("audit_review requires payload.review")
        if message_type == "conflict_notice" and "conflict_type" not in payload:
            errors.append("conflict_notice requires payload.conflict_type")
        if message_type == "memory_update" and "memory_key" not in payload:
            errors.append("memory_update requires payload.memory_key")
