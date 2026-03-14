"""Integration tests for message bus with multi-agent dispatcher."""

from __future__ import annotations

import time
import unittest
from typing import List

from src.messaging.in_memory_bus import InMemoryMessageBus
from src.messaging.interfaces import Message
from src.multi_agent.dispatcher import TaskAssignment, TaskDispatcher


class TestDispatcherWithMessageBus(unittest.TestCase):

    def test_enqueue_publishes_event(self):
        bus = InMemoryMessageBus()
        dispatcher = TaskDispatcher(message_bus=bus)
        events: List[Message] = []
        bus.subscribe("task.assigned.planner", events.append)

        dispatcher.enqueue(TaskAssignment(
            task_id="t1", role="planner", payload={"goal": "test"},
        ))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["task_id"], "t1")
        bus.close()

    def test_complete_publishes_event(self):
        bus = InMemoryMessageBus()
        dispatcher = TaskDispatcher(message_bus=bus)
        events: List[Message] = []
        bus.subscribe("task.completed", events.append)

        dispatcher.enqueue(TaskAssignment(
            task_id="t2", role="executor", payload={},
        ))
        dispatcher.dispatch_next("executor")
        dispatcher.complete("t2", succeeded=True)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].payload["succeeded"])
        bus.close()

    def test_dispatcher_without_bus_still_works(self):
        dispatcher = TaskDispatcher()
        dispatcher.enqueue(TaskAssignment(task_id="t3", role="r", payload={}))
        got = dispatcher.dispatch_next("r")
        self.assertEqual(got.task_id, "t3")

    def test_cross_agent_request_reply(self):
        bus = InMemoryMessageBus()

        def _agent_b_handler(msg: Message):
            if msg.reply_to:
                bus.reply(msg, {"result": "done"}, sender_id="agent-b")

        bus.subscribe("agent-b.work", _agent_b_handler)
        reply = bus.request("agent-b.work", {"task": "analyze"}, sender_id="agent-a", timeout=2.0)
        self.assertIsNotNone(reply)
        self.assertEqual(reply.payload["result"], "done")
        bus.close()


if __name__ == "__main__":
    unittest.main()
