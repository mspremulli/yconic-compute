from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any


class TaskType(Enum):
    CODE = "code"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    GENERAL = "general"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReasoningStrategy(Enum):
    COT = "CoT"
    TOT = "ToT"
    REACT = "ReAct"
    PLAN_AND_EXECUTE = "PlanAndExecute"


class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    description: str
    task_type: TaskType = TaskType.GENERAL
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    assigned_agent: str | None = None
    deadline: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: str | None = None
    retry_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "task_type": self.task_type.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "retry_count": self.retry_count,
        }


@dataclass
class TaskGraph:
    tasks: dict[str, Task] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def add_edge(self, from_id: str, to_id: str) -> None:
        self.edges.append((from_id, to_id))
        if from_id in self.tasks and to_id in self.tasks:
            self.tasks[to_id].dependencies.append(from_id)

    def get_ready_tasks(self) -> list[Task]:
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps_complete = all(
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            if deps_complete:
                ready.append(task)
        return sorted(ready, key=lambda t: t.priority, reverse=True)

    def mark_complete(self, task_id: str) -> list[Task]:
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.COMPLETED
        return self.get_ready_tasks()

    def is_complete(self) -> bool:
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks.values())

    def has_failures(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())
