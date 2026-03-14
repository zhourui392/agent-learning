"""Contract tests for MessageBus implementations."""

from __future__ import annotations

import threading
import time
import unittest
from typing import List

from src.messaging.interfaces import Message
from src.messaging.in_memory_bus import InMemoryMessageBus

try:
    import fakeredis
    from src.messaging.redis_bus import RedisMessageBus
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False


def _create_buses():
    """Yield (name, bus) pairs for parametric testing."""
    yield "in_memory", InMemoryMessageBus()
    if HAS_FAKEREDIS:
        yield "redis", RedisMessageBus()


class TestMessageBusContract(unittest.TestCase):
    """Shared contract tests run against every implementation."""

    def _run_for_all(self, test_fn):
        for name, bus in _create_buses():
            with self.subTest(backend=name):
                try:
                    test_fn(bus)
                finally:
                    bus.close()

    def test_publish_subscribe_basic(self):
        def _test(bus):
            received: List[Message] = []
            bus.subscribe("events", received.append)
            bus.publish("events", {"key": "value"})
            # For redis bus, messages arrive asynchronously
            time.sleep(0.2)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].payload["key"], "value")
            self.assertEqual(received[0].topic, "events")
        self._run_for_all(_test)

    def test_multiple_subscribers(self):
        def _test(bus):
            a: List[Message] = []
            b: List[Message] = []
            bus.subscribe("multi", a.append)
            bus.subscribe("multi", b.append)
            bus.publish("multi", "hello")
            time.sleep(0.2)
            self.assertEqual(len(a), 1)
            self.assertEqual(len(b), 1)
        self._run_for_all(_test)

    def test_unsubscribe(self):
        def _test(bus):
            received: List[Message] = []
            bus.subscribe("unsub", received.append)
            self.assertTrue(bus.unsubscribe("unsub", received.append))
            bus.publish("unsub", "gone")
            time.sleep(0.2)
            self.assertEqual(len(received), 0)
        self._run_for_all(_test)

    def test_topic_isolation(self):
        def _test(bus):
            a_msgs: List[Message] = []
            b_msgs: List[Message] = []
            bus.subscribe("topic.a", a_msgs.append)
            bus.subscribe("topic.b", b_msgs.append)
            bus.publish("topic.a", "a-data")
            time.sleep(0.2)
            self.assertEqual(len(a_msgs), 1)
            self.assertEqual(len(b_msgs), 0)
        self._run_for_all(_test)

    def test_subscriber_count(self):
        def _test(bus):
            self.assertEqual(bus.topic_subscriber_count("empty"), 0)
            handler = lambda m: None
            bus.subscribe("counted", handler)
            self.assertEqual(bus.topic_subscriber_count("counted"), 1)
            bus.unsubscribe("counted", handler)
            self.assertEqual(bus.topic_subscriber_count("counted"), 0)
        self._run_for_all(_test)

    def test_request_reply(self):
        def _test(bus):
            def _responder(msg: Message):
                if msg.reply_to:
                    bus.reply(msg, {"answer": 42})
            bus.subscribe("question", _responder)
            reply = bus.request("question", {"q": "meaning"}, timeout=2.0)
            self.assertIsNotNone(reply)
            self.assertEqual(reply.payload["answer"], 42)
        self._run_for_all(_test)

    def test_request_timeout(self):
        def _test(bus):
            reply = bus.request("nobody", {"q": "hello"}, timeout=0.2)
            self.assertIsNone(reply)
        self._run_for_all(_test)


if __name__ == "__main__":
    unittest.main()
