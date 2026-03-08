"""Tests for W7 multi-agent protocol validator."""

from __future__ import annotations

import unittest

from src.multi_agent.protocol_validator import ProtocolValidator


class ProtocolValidatorTestCase(unittest.TestCase):
    """Verify W7 protocol validation behavior."""

    def test_validate_message_accepts_valid_payload(self) -> None:
        validator = ProtocolValidator()
        message = {
            "version": "1.0.0",
            "header": {
                "message_id": "msg-1",
                "message_type": "task_request",
                "sender_role": "planner",
                "receiver_role": "executor",
                "task_id": "task-1",
            },
            "payload": {"instruction": "collect refund evidence"},
            "meta": {
                "trace_id": "trace-1",
                "session_id": "sess-1",
                "status": "pending",
                "priority": 2,
                "conflict_fields": [],
            },
        }

        result = validator.validate_message(message)

        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_validate_message_rejects_missing_instruction(self) -> None:
        validator = ProtocolValidator()
        message = {
            "version": "1.0.0",
            "header": {
                "message_id": "msg-1",
                "message_type": "task_request",
                "sender_role": "planner",
                "receiver_role": "executor",
                "task_id": "task-1",
            },
            "payload": {},
            "meta": {
                "trace_id": "trace-1",
                "session_id": "sess-1",
                "status": "pending",
                "priority": 2,
                "conflict_fields": [],
            },
        }

        result = validator.validate_message(message)

        self.assertFalse(result.valid)
        self.assertIn("task_request requires payload.instruction", result.errors)


if __name__ == "__main__":
    unittest.main()
