"""Agent messaging system"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, List
import uuid


class MessageType(str, Enum):
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    FINDING_SHARE = "finding_share"
    EVIDENCE_REQUEST = "evidence_request"
    EVIDENCE_RESPONSE = "evidence_response"
    RESOURCE_REQUEST = "resource_request"
    RESPONSE_RESPONSE = "resource_response"
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    CANCEL = "cancel"


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.TASK_REQUEST
    sender_id: str = ""
    recipient_id: str = ""
    parent_id: Optional[str] = None  # For request-response correlation
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl: int = 300  # Time to live in seconds
    priority: int = 0  # Higher = more urgent

    def is_expired(self) -> bool:
        """Check if message is expired."""
        elapsed = (datetime.utcnow() - self.timestamp).total_seconds()
        return elapsed > self.ttl

    def create_response(self, payload: Dict[str, Any]) -> "AgentMessage":
        """Create a response message."""
        return AgentMessage(
            type=MessageType.TASK_RESPONSE,
            sender_id=self.recipient_id,
            recipient_id=self.sender_id,
            parent_id=self.id,
            payload=payload,
        )


class MessageBus:
    """In-memory message bus for agent communication."""

    def __init__(self):
        self._queues: Dict[str, List[AgentMessage]] = {}
        self._subscriptions: Dict[str, List[Callable[[AgentMessage], Any]]] = {}

    def send(self, message: AgentMessage):
        """Send a message to a recipient."""
        if message.recipient_id not in self._queues:
            self._queues[message.recipient_id] = []
        self._queues[message.recipient_id].append(message)

        # Notify subscribers
        for callback in self._subscriptions.get(message.recipient_id, []):
            try:
                callback(message)
            except Exception:
                pass  # Ignore callback errors

    def receive(self, agent_id: str, max_messages: int = 10) -> List[AgentMessage]:
        """Receive messages for an agent."""
        queue = self._queues.get(agent_id, [])
        messages = queue[:max_messages]
        self._queues[agent_id] = queue[max_messages:]
        return messages

    def subscribe(self, agent_id: str, callback: Callable[[AgentMessage], Any]):
        """Subscribe to messages for an agent."""
        if agent_id not in self._subscriptions:
            self._subscriptions[agent_id] = []
        self._subscriptions[agent_id].append(callback)

    def unsubscribe(self, agent_id: str, callback: Callable[[AgentMessage], Any]):
        """Unsubscribe from messages."""
        if agent_id in self._subscriptions:
            try:
                self._subscriptions[agent_id].remove(callback)
            except ValueError:
                pass

    def broadcast(self, message: AgentMessage, exclude: Optional[List[str]] = None):
        """Broadcast message to all agents except excluded."""
        exclude = exclude or []
        for agent_id in self._queues:
            if agent_id not in exclude:
                msg = AgentMessage(
                    type=message.type,
                    sender_id=message.sender_id,
                    recipient_id=agent_id,
                    parent_id=message.id,
                    payload=message.payload.copy(),
                    priority=message.priority,
                )
                self.send(msg)


# Global message bus
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get global message bus."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus