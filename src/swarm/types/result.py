from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskResult:
    task_id: str
    success: bool
    final_answer: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    agent_traces: dict[str, list[str]] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    error: str | None = None
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "final_answer": self.final_answer,
            "artifacts": self.artifacts,
            "agent_traces": self.agent_traces,
            "execution_time_seconds": self.execution_time_seconds,
            "error": self.error,
            "completed_at": self.completed_at.isoformat(),
        }


@dataclass
class ExecutionStatus:
    task_id: str
    status: str
    completed_tasks: int
    total_tasks: int
    running_agents: list[str]
    failed_tasks: list[str]
    progress_percent: float
