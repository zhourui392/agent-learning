"""Tests for TrafficAnonymizer."""

import unittest

from src.replay.anonymizer import TrafficAnonymizer


class TestTrafficAnonymizer(unittest.TestCase):
    def setUp(self):
        self.anon = TrafficAnonymizer()

    def test_phone_anonymized(self):
        result = self.anon.anonymize_text("call me at 13812345678")
        self.assertIn("<PHONE>", result)
        self.assertNotIn("13812345678", result)

    def test_email_anonymized(self):
        result = self.anon.anonymize_text("email: user@example.com")
        self.assertIn("<EMAIL>", result)
        self.assertNotIn("user@example.com", result)

    def test_id_card_anonymized(self):
        result = self.anon.anonymize_text("id: 110101199001011234")
        self.assertIn("<ID_CARD>", result)

    def test_anonymize_record_deep_walk(self):
        record = {
            "case_id": "c1",
            "sample": {
                "query": "call 13912345678",
                "nested": ["email: foo@bar.com"],
            },
        }
        result = self.anon.anonymize_record(record)
        self.assertIn("<PHONE>", result["sample"]["query"])
        self.assertIn("<EMAIL>", result["sample"]["nested"][0])

    def test_non_string_values_preserved(self):
        record = {"count": 42, "flag": True, "rate": 0.5}
        result = self.anon.anonymize_record(record)
        self.assertEqual(result["count"], 42)
        self.assertEqual(result["flag"], True)
        self.assertEqual(result["rate"], 0.5)

    def test_custom_patterns(self):
        anon = TrafficAnonymizer(patterns=[(r"\d{4}-\d{4}", "<CARD>")])
        result = anon.anonymize_text("card: 1234-5678")
        self.assertIn("<CARD>", result)


if __name__ == "__main__":
    unittest.main()
