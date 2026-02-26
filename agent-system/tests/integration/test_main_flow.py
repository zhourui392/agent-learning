"""
Integration tests for main flow.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.api.app import AgentApplication


class MainFlowIntegrationTestCase(unittest.TestCase):
    """
    Verifies end-to-end execution, policy deny, and snapshot persistence.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Build application and fixture path.

        @param cls: Test class.
        @return: None.
        """
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.fixture_path = cls.project_root / "tests" / "fixtures" / "sample_request.json"

    def setUp(self) -> None:
        """
        Create isolated app per test to avoid state leakage.

        @param self: Test instance.
        @return: None.
        """
        self.app = AgentApplication(project_root=self.project_root)

    def test_main_flow_success(self) -> None:
        """
        Search flow should succeed and return step results.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        response = self.app.handle_request(request_payload)

        self.assertTrue(response["success"])
        self.assertIsNone(response["error"])
        self.assertEqual(response["session_id"], request_payload["session_id"])
        self.assertGreaterEqual(len(response["data"]["step_results"]), 1)

    def test_notify_flow_denied_without_approval_token(self) -> None:
        """
        Notify flow should fail when approval token is missing.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["session_id"] = "sess-notify-deny"
        request_payload["request_id"] = "req-notify-deny"
        request_payload["user_input"] = "notify team about deployment"
        request_payload["allowed_tools"] = ["tool.notify"]
        request_payload["metadata"] = {"recipient": "ops-team"}

        response = self.app.handle_request(request_payload)

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "permission_denied")

    def test_snapshot_exists_after_execution(self) -> None:
        """
        Successful flow should produce at least one snapshot.

        @param self: Test instance.
        @return: None.
        """
        request_payload = self._load_fixture()
        request_payload["session_id"] = "sess-snapshot"
        request_payload["request_id"] = "req-snapshot"

        self.app.handle_request(request_payload)
        snapshot = self.app.get_session_snapshot("sess-snapshot")

        self.assertIsNotNone(snapshot)
        self.assertIn("snapshot_id", snapshot)

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
