"""Tests for W7 dispatcher and callback handler."""

from __future__ import annotations

import unittest

from src.multi_agent.callback_handler import CallbackHandler, CallbackRecord
from src.multi_agent.dispatcher import TaskAssignment, TaskDispatcher


class DispatcherCallbackTestCase(unittest.TestCase):
    """Verify dispatching and callback aggregation."""

    def test_dispatch_and_complete_assignment(self) -> None:
        dispatcher = TaskDispatcher()
        assignment = TaskAssignment(task_id="task-1", role="executor", payload={"x": 1})
        dispatcher.enqueue(assignment)

        running = dispatcher.dispatch_next("executor")
        completed = dispatcher.complete("task-1", succeeded=True)

        self.assertEqual(running.status, "completed")
        self.assertEqual(completed.status, "completed")

    def test_callback_handler_aggregates_task_records(self) -> None:
        handler = CallbackHandler()
        handler.record(CallbackRecord(task_id="task-1", role="executor", succeeded=True, payload={}))
        handler.record(CallbackRecord(task_id="task-1", role="auditor", succeeded=True, payload={}))

        aggregated = handler.aggregate_task("task-1")

        self.assertEqual(aggregated["callback_count"], 2)
        self.assertTrue(aggregated["all_succeeded"])


if __name__ == "__main__":
    unittest.main()
