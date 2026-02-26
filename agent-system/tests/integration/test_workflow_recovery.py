"""
Integration tests for timeout, retry, and idempotent recovery.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.api.app import AgentApplication


class WorkflowRecoveryIntegrationTestCase(unittest.TestCase):
    """
    Verify workflow recovery behavior in W2.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Build application fixture path.

        @param cls: Test class.
        @return: None.
        """
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.fixture_path = cls.project_root / "tests" / "fixtures" / "sample_request.json"

    def setUp(self) -> None:
        """
        Create isolated app per test.

        @param self: Test instance.
        @return: None.
        """
        self.app = AgentApplication(project_root=self.project_root)

    def test_timeout_failure_should_be_recorded(self) -> None:
        """
        Slow tool step should fail with timeout or retry_exhausted.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["request_id"] = "req-timeout"
        request_payload["session_id"] = "sess-timeout"
        request_payload["user_input"] = "search sleep_short"
        request_payload["allowed_tools"] = ["tool.search"]
        request_payload["metadata"] = {
            "step_timeout_seconds": 1,
            "execution_control": {
                "session_timeout_seconds": 30,
                "max_concurrency": 1,
            },
        }

        response = self.app.handle_request(request_payload)

        self.assertFalse(response["success"])
        self.assertIn(response["error"]["code"], {"tool_timeout", "retry_exhausted"})

    def test_retryable_failure_should_succeed_after_retry(self) -> None:
        """
        Flaky tool should succeed within retry budget.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["request_id"] = "req-retry-success"
        request_payload["session_id"] = "sess-retry-success"
        request_payload["user_input"] = "search flaky_once"
        request_payload["allowed_tools"] = ["tool.search"]

        response = self.app.handle_request(request_payload)

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertGreaterEqual(len(response["data"]["step_results"]), 1)

    def test_duplicate_submit_should_skip_completed_step(self) -> None:
        """
        Replaying same request/session should not re-run completed step.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["request_id"] = "req-idempotent"
        request_payload["session_id"] = "sess-idempotent"
        request_payload["user_input"] = "search architecture baseline"
        request_payload["allowed_tools"] = ["tool.search"]

        first_response = self.app.handle_request(request_payload)
        second_response = self.app.handle_request(request_payload)

        self.assertTrue(first_response["success"])
        self.assertTrue(second_response["success"])

        session_state = self.app._state_store.get_session("sess-idempotent")  # pylint: disable=protected-access
        attempts = session_state.steps["step-1"].attempts
        self.assertEqual(attempts, 1)

    def _load_fixture(self) -> dict:
        """
        Load request fixture.

        @param self: Test instance.
        @return: Parsed request dictionary.
        """
        with self.fixture_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)


if __name__ == "__main__":
    unittest.main()
