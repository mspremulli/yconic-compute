from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class ToolResultStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str
    agent_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    requires_confirmation: bool = False
    enabled: bool = True

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    async def execute(self, arguments: dict[str, Any]) -> ToolResult: ...
