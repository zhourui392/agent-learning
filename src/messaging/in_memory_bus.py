"""Threading-based in-memory message bus."""

from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from src.messaging.interfaces import Message, MessageBus, MessageHandler


class InMemoryMessageBus(MessageBus):
    """In-process message bus backed by threading primitives."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[MessageHandler]] = {}
        self._lock = threading.Lock()
        self._closed = False

    # -- publish / subscribe --------------------------------------------------

    def publish(self, topic: str, payload: Any, sender_id: str = "") -> Message:
        msg = Message(topic=topic, payload=payload, sender_id=sender_id)
        self._dispatch(topic, msg)
        return msg

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(handler)

    def unsubscribe(self, topic: str, handler: MessageHandler) -> bool:
        with self._lock:
            handlers = self._subscribers.get(topic, [])
            if handler in handlers:
                handlers.remove(handler)
                return True
            return False

    def topic_subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._subscribers.get(topic, []))

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
            self._dispatch(topic, msg)
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
        self._dispatch(original.reply_to, msg)
        return msg

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._subscribers.clear()

    # -- internal -------------------------------------------------------------

    def _dispatch(self, topic: str, msg: Message) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(topic, []))
        for handler in handlers:
            handler(msg)
