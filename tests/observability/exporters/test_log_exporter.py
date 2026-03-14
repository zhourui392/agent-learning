"""Tests for JsonFileLogExporter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.observability.exporters.json_log_exporter import JsonFileLogExporter


class TestJsonFileLogExporter(unittest.TestCase):

    def test_export_and_flush(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "logs.jsonl")
            exporter = JsonFileLogExporter(path, max_buffer=100)
            entries = [{"level": "INFO", "message": f"msg_{i}"} for i in range(3)]
            count = exporter.export(entries)
            self.assertEqual(count, 3)
            exporter.flush()
            lines = Path(path).read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0])["message"], "msg_0")

    def test_auto_flush_on_buffer_full(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "logs.jsonl")
            exporter = JsonFileLogExporter(path, max_buffer=2)
            exporter.export([{"a": 1}])
            self.assertFalse(Path(path).exists())
            exporter.export([{"a": 2}])  # triggers auto-flush
            self.assertTrue(Path(path).exists())

    def test_empty_flush(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "logs.jsonl")
            exporter = JsonFileLogExporter(path)
            exporter.flush()  # should not create file
            self.assertFalse(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
