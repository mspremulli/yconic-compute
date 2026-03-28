from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from enum import Enum


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class AgentMessage:
    id: str
    sender: str
    topic: str
    payload: dict[str, Any]
    recipients: list[str] | None = None
    reply_to: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = MessagePriority.NORMAL.value
    correlation_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "topic": self.topic,
            "payload": self.payload,
            "recipients": self.recipients,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "correlation_id": self.correlation_id,
        }


STANDARD_TOPICS = {
    "task.assigned": "task.assigned",
    "task.completed": "task.completed",
    "task.failed": "task.failed",
    "code.generated": "code.generated",
    "code.reviewed": "code.reviewed",
    "research.findings": "research.findings",
    "memory.stored": "memory.stored",
    "ping": "ping",
}
