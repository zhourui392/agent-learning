"""Abstract message bus interface for distributed agent communication."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Message:
    """One message traveling through the bus."""

    topic: str
    payload: Any
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sender_id: str = ""
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None


MessageHandler = Callable[[Message], None]


class MessageBus(ABC):
    """Publish/subscribe + request-reply message bus contract."""

    @abstractmethod
    def publish(self, topic: str, payload: Any, sender_id: str = "") -> Message:
        """Publish a message to a topic."""

    @abstractmethod
    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Register a handler for a topic."""

    @abstractmethod
    def unsubscribe(self, topic: str, handler: MessageHandler) -> bool:
        """Remove a handler.  Return ``True`` if it was found."""

    @abstractmethod
    def request(
        self,
        topic: str,
        payload: Any,
        sender_id: str = "",
        timeout: float = 5.0,
    ) -> Optional[Message]:
        """Synchronous request-reply.  Return the reply or ``None`` on timeout."""

    @abstractmethod
    def reply(self, original: Message, payload: Any, sender_id: str = "") -> Message:
        """Reply to a request message."""

    @abstractmethod
    def topic_subscriber_count(self, topic: str) -> int:
        """Return the number of subscribers on a topic."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
