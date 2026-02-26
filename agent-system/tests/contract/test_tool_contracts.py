"""
Contract validation tests.

@author zhourui(V33215020)
@since 2026/02/26
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.gateway.validator import ContractValidationError, ContractValidator


class ToolContractTestCase(unittest.TestCase):
    """
    Verifies tool contract behavior for valid and invalid payloads.

    @author zhourui(V33215020)
    @since 2026/02/26
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Build shared contract validator.

        @param cls: Test class.
        @return: None.
        """
        contracts_root = Path(__file__).resolve().parents[2] / "contracts"
        cls.validator = ContractValidator(contracts_root=contracts_root)

    def test_search_contract_accepts_valid_payload(self) -> None:
        """
        Search payload should pass with required fields.

        @param self: Test instance.
        @return: None.
        """
        payload = {
            "query": "architecture",
            "top_k": 5,
            "runtime_context": {"task": {"request_id": "req-1"}},
        }
        self.validator.validate("tools/tool.search.schema.json", payload)

    def test_search_contract_rejects_missing_required_field(self) -> None:
        """
        Search payload should fail when query is missing.

        @param self: Test instance.
        @return: None.
        """
        with self.assertRaises(ContractValidationError):
            self.validator.validate(
                "tools/tool.search.schema.json",
                {"top_k": 5, "runtime_context": {}},
            )

    def test_search_contract_rejects_type_error(self) -> None:
        """
        Search payload should fail when top_k type is invalid.

        @param self: Test instance.
        @return: None.
        """
        with self.assertRaises(ContractValidationError):
            self.validator.validate(
                "tools/tool.search.schema.json",
                {"query": "ok", "top_k": "five", "runtime_context": {}},
            )

    def test_search_contract_rejects_out_of_range(self) -> None:
        """
        Search payload should fail when top_k exceeds max value.

        @param self: Test instance.
        @return: None.
        """
        with self.assertRaises(ContractValidationError):
            self.validator.validate(
                "tools/tool.search.schema.json",
                {"query": "ok", "top_k": 99, "runtime_context": {}},
            )


if __name__ == "__main__":
    unittest.main()
