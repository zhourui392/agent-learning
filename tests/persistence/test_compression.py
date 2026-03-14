"""Tests for compressed serialization utilities."""

from __future__ import annotations

import unittest

from src.persistence.compression import deserialize_compressed, serialize_compressed


class TestCompression(unittest.TestCase):

    def test_small_value_not_compressed(self):
        data = serialize_compressed({"key": "value"}, threshold=1024)
        self.assertEqual(data[0:1], b"\x00")  # plain marker
        result = deserialize_compressed(data)
        self.assertEqual(result, {"key": "value"})

    def test_large_value_compressed(self):
        large = {"data": "x" * 2000}
        data = serialize_compressed(large, threshold=1024)
        self.assertEqual(data[0:1], b"\x01")  # compressed marker
        result = deserialize_compressed(data)
        self.assertEqual(result, large)

    def test_roundtrip_various_types(self):
        for value in [42, "hello", [1, 2, 3], {"nested": {"a": 1}}, None, True]:
            with self.subTest(value=value):
                data = serialize_compressed(value, threshold=0)  # force compress
                self.assertEqual(deserialize_compressed(data), value)

    def test_empty_bytes(self):
        self.assertIsNone(deserialize_compressed(b""))


if __name__ == "__main__":
    unittest.main()
