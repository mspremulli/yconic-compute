import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass
import structlog

from swarm.db.connection import Database

logger = structlog.get_logger()


@dataclass
class AuditEntry:
    id: str
    agent_id: str | None
    task_id: str | None
    action: str
    details: dict[str, Any] | None
    outcome: str | None
    execution_time_ms: float | None
    created_at: datetime


class AuditLogger:
    def __init__(self, db: Database):
        self.db = db

    async def log(
        self,
        action: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
        outcome: str | None = None,
        execution_time_ms: float | None = None,
    ) -> str:
        entry_id = str(uuid.uuid4())

        await self.db.execute(
            """INSERT INTO audit_log 
               (id, agent_id, task_id, action, details, outcome, execution_time_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry_id,
                agent_id,
                task_id,
                action,
                str(details) if details else None,
                outcome,
                execution_time_ms,
                datetime.utcnow().isoformat(),
            ),
        )

        logger.debug(
            "audit_logged",
            entry_id=entry_id,
            action=action,
            agent_id=agent_id,
            task_id=task_id,
        )

        return entry_id

    async def log_agent_start(self, agent_id: str, task_id: str, prompt: str) -> str:
        return await self.log(
            action="agent.start",
            agent_id=agent_id,
            task_id=task_id,
            details={"prompt": prompt[:500]},
        )

    async def log_agent_end(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        output: str | None = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ) -> str:
        return await self.log(
            action="agent.end",
            agent_id=agent_id,
            task_id=task_id,
            details={"output_length": len(output) if output else 0, "error": error},
            outcome="success" if success else "failure",
            execution_time_ms=duration_ms,
        )

    async def log_tool_call(
        self,
        agent_id: str,
        task_id: str,
        tool_name: str,
        success: bool,
        duration_ms: float = 0.0,
    ) -> str:
        return await self.log(
            action="tool.call",
            agent_id=agent_id,
            task_id=task_id,
            details={"tool_name": tool_name},
            outcome="success" if success else "failure",
            execution_time_ms=duration_ms,
        )

    async def log_message_sent(
        self,
        sender: str,
        recipient: str,
        topic: str,
        task_id: str | None = None,
    ) -> str:
        return await self.log(
            action="message.sent",
            agent_id=sender,
            task_id=task_id,
            details={"recipient": recipient, "topic": topic},
        )

    async def get_recent(
        self,
        agent_id: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        return [
            AuditEntry(
                id=row["id"],
                agent_id=row["agent_id"],
                task_id=row["task_id"],
                action=row["action"],
                details=eval(row["details"]) if row["details"] else None,
                outcome=row["outcome"],
                execution_time_ms=row["execution_time_ms"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
