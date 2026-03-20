"""Tests for InMemoryReplayEngine."""

import json
import tempfile
import unittest
from pathlib import Path

from src.replay.models import ReplayPolicy, ReplayRecord, ReplayResult
from src.replay.replay_engine import InMemoryReplayEngine


class TestInMemoryReplayEngine(unittest.TestCase):
    def setUp(self):
        self.engine = InMemoryReplayEngine()

    def test_capture_anonymizes(self):
        record = ReplayRecord(
            case_id="c1",
            sample={"query": "call 13812345678"},
        )
        self.engine.capture(record)
        stored = self.engine.list_records()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].anonymized)
        self.assertNotIn("13812345678", stored[0].sample.get("query", ""))

    def test_capture_already_anonymized(self):
        record = ReplayRecord(case_id="c2", anonymized=True, sample={"q": "safe"})
        self.engine.capture(record)
        stored = self.engine.list_records()
        self.assertEqual(stored[0].sample["q"], "safe")

    def test_load_from_jsonl(self):
        records = [
            {"case_id": "c1", "error_code": "E1", "answer_f1": 0.3, "sample": {"query": "q1"}},
            {"case_id": "c2", "error_code": "E2", "answer_f1": 0.1, "sample": {"query": "q2"}},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            for r in records:
                json.dump(r, f, ensure_ascii=False)
                f.write("\n")
            path = f.name

        count = self.engine.load_from_jsonl(path)
        self.assertEqual(count, 2)
        self.assertEqual(len(self.engine.list_records()), 2)

    def test_replay_executes_all(self):
        for i in range(5):
            self.engine.capture(ReplayRecord(case_id=f"c{i}", anonymized=True))

        def executor(rec):
            return ReplayResult(record_id=rec.case_id, success=True, latency_ms=1.0)

        batch = self.engine.replay(ReplayPolicy(max_batch_size=10), executor)
        self.assertEqual(len(batch.results), 5)
        self.assertTrue(all(r.success for r in batch.results))

    def test_replay_respects_max_batch_size(self):
        for i in range(10):
            self.engine.capture(ReplayRecord(case_id=f"c{i}", anonymized=True))

        def executor(rec):
            return ReplayResult(record_id=rec.case_id, success=True)

        batch = self.engine.replay(ReplayPolicy(max_batch_size=3), executor)
        self.assertLessEqual(len(batch.results), 3)

    def test_clear(self):
        self.engine.capture(ReplayRecord(case_id="c1", anonymized=True))
        self.engine.clear()
        self.assertEqual(len(self.engine.list_records()), 0)


if __name__ == "__main__":
    unittest.main()
