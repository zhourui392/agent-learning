"""Redis-backed message bus using fakeredis for simulation."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

try:
    import fakeredis
except ImportError:  # pragma: no cover
    fakeredis = None  # type: ignore[assignment]

from src.messaging.interfaces import Message, MessageBus, MessageHandler


def _serialize_message(msg: Message) -> str:
    data = asdict(msg)
    return json.dumps(data, ensure_ascii=False, default=str)


def _deserialize_message(raw: str) -> Message:
    data = json.loads(raw)
    return Message(**data)


class RedisMessageBus(MessageBus):
    """Message bus backed by Redis pub/sub (fakeredis for simulation).

    All ``FakeRedis`` instances must share the same ``FakeServer`` so that
    pub/sub works across connections.
    """

    def __init__(
        self,
        server: Optional[Any] = None,
    ) -> None:
        if fakeredis is None:
            raise RuntimeError("fakeredis is required: pip install fakeredis")
        self._server = server or fakeredis.FakeServer()
        self._pub_client = fakeredis.FakeRedis(server=self._server)
        self._sub_client = fakeredis.FakeRedis(server=self._server)
        self._pubsub = self._sub_client.pubsub()
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._lock = threading.Lock()
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False

    # -- publish / subscribe --------------------------------------------------

    def publish(self, topic: str, payload: Any, sender_id: str = "") -> Message:
        msg = Message(topic=topic, payload=payload, sender_id=sender_id)
        self._pub_client.publish(topic, _serialize_message(msg))
        return msg

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        with self._lock:
            is_new_topic = topic not in self._handlers
            self._handlers.setdefault(topic, []).append(handler)
        if is_new_topic:
            self._pubsub.subscribe(topic)
        self._ensure_listener()

    def unsubscribe(self, topic: str, handler: MessageHandler) -> bool:
        with self._lock:
            handlers = self._handlers.get(topic, [])
            if handler in handlers:
                handlers.remove(handler)
                if not handlers:
                    self._pubsub.unsubscribe(topic)
                    del self._handlers[topic]
                return True
            return False

    def topic_subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._handlers.get(topic, []))

    # -- request / reply ------------------------------------------------------

    def request(
        self,
        topic: str,
        payload: Any,
        sender_id: str = "",
        timeout: float = 5.0,
    ) -> Optional[Message]:
        reply_topic = f"_reply.{uuid.uuid4().hex}"
        event = threading.Event()
        result: List[Message] = []

        def _on_reply(msg: Message) -> None:
            result.append(msg)
            event.set()

        self.subscribe(reply_topic, _on_reply)
        try:
            msg = Message(
                topic=topic,
                payload=payload,
                sender_id=sender_id,
                reply_to=reply_topic,
            )
            self._pub_client.publish(topic, _serialize_message(msg))
            event.wait(timeout=timeout)
            return result[0] if result else None
        finally:
            self.unsubscribe(reply_topic, _on_reply)

    def reply(self, original: Message, payload: Any, sender_id: str = "") -> Message:
        if not original.reply_to:
            raise ValueError("original message has no reply_to topic")
        msg = Message(
            topic=original.reply_to,
            payload=payload,
            sender_id=sender_id,
            correlation_id=original.message_id,
        )
        self._pub_client.publish(original.reply_to, _serialize_message(msg))
        return msg

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        self._running = False
        self._pubsub.unsubscribe()
        self._pubsub.close()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        with self._lock:
            self._handlers.clear()

    # -- internal -------------------------------------------------------------

    def _ensure_listener(self) -> None:
        if self._running:
            return
        self._running = True
        self._listener_thread = threading.Thread(
            target=self._listen_loop, daemon=True,
        )
        self._listener_thread.start()

    def _listen_loop(self) -> None:
        while self._running:
            try:
                raw_message = self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1,
                )
            except Exception:
                break
            if raw_message is None:
                continue
            if raw_message["type"] != "message":
                continue
            topic = raw_message["channel"]
            if isinstance(topic, bytes):
                topic = topic.decode("utf-8")
            data = raw_message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            msg = _deserialize_message(data)
            with self._lock:
                handlers = list(self._handlers.get(topic, []))
            for handler in handlers:
                handler(msg)
