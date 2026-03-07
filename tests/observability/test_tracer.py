"""Unit tests for W6 tracer and logger."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.observability.logger import StructuredLogger
from src.observability.tracer import TraceContext, Tracer


class TracerLoggerTestCase(unittest.TestCase):
    """Verify trace and log persistence."""

    def test_tracer_and_logger_write_jsonl(self) -> None:
        """Tracer and logger should persist structured JSONL records."""

        tracer = Tracer()
        logger = StructuredLogger()
        trace_context = TraceContext(trace_id="trace-1", session_id="sess-1", case_id="case-1")

        with tracer.start_span(trace_context, "retrieval", "retrieve") as span_scope:
            logger.info(
                "retrieval",
                "retrieval_complete",
                "Retriever completed",
                trace_context,
                span_scope.step_id,
                {"chunk_count": 2},
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "traces.jsonl"
            log_path = Path(temp_dir) / "logs.jsonl"
            tracer.write_jsonl(str(trace_path))
            logger.write_jsonl(str(log_path))

            trace_records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
            log_records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(trace_records[0]["trace_id"], "trace-1")
            self.assertEqual(trace_records[0]["component"], "retrieval")
            self.assertEqual(log_records[0]["step_id"], trace_records[0]["step_id"])
            self.assertEqual(log_records[0]["event_type"], "retrieval_complete")


if __name__ == "__main__":
    unittest.main()
