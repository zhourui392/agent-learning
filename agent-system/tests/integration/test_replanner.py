"""
Integration tests for replanner behavior.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.api.app import AgentApplication


class ReplannerIntegrationTestCase(unittest.TestCase):
    """
    Verify replanner recovery and no-replan boundaries.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Build fixture path.

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

    def test_retry_exhausted_should_replan_and_succeed(self) -> None:
        """
        Retry-exhausted step should trigger local_replace replanning.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["request_id"] = "req-replan-success"
        request_payload["session_id"] = "sess-replan-success"
        request_payload["user_input"] = "search flaky_twice"
        request_payload["allowed_tools"] = ["tool.search"]

        response = self.app.handle_request(request_payload)

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])

        replan_history = response["data"].get("replan_history", [])
        self.assertGreaterEqual(len(replan_history), 1)
        self.assertEqual(replan_history[0]["strategy"], "local_replace")

        step_results = response["data"]["step_results"]
        self.assertGreaterEqual(len(step_results), 2)
        self.assertFalse(step_results[0]["result"]["success"])
        self.assertTrue(step_results[-1]["result"]["success"])

    def test_non_retryable_error_should_not_replan(self) -> None:
        """
        Non-retryable business error should fail without replanning.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["request_id"] = "req-replan-no"
        request_payload["session_id"] = "sess-replan-no"
        request_payload["user_input"] = "search force_fail"
        request_payload["allowed_tools"] = ["tool.search"]

        response = self.app.handle_request(request_payload)

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "invalid_business_input")

        session_state = self.app._state_store.get_session("sess-replan-no")  # pylint: disable=protected-access
        self.assertEqual(len(session_state.step_sequence), 1)

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
