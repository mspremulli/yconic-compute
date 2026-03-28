from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import structlog

from swarm.db.connection import Database

logger = structlog.get_logger()


@dataclass
class Episode:
    id: str
    agent_id: str
    task_id: str
    event_type: str
    content: str
    importance_score: int = 5
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "content": self.content,
            "importance_score": self.importance_score,
            "created_at": self.created_at.isoformat(),
        }


class EpisodicMemory:
    def __init__(self, db: Database, retention_days: int = 30):
        self.db = db
        self.retention_days = retention_days

    async def store(self, episode: Episode) -> str:
        await self.db.execute(
            """INSERT INTO episodes 
               (id, agent_id, task_id, event_type, content, importance_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                episode.id,
                episode.agent_id,
                episode.task_id,
                episode.event_type,
                episode.content,
                episode.importance_score,
                episode.created_at.isoformat(),
            ),
        )
        logger.debug("episode_stored", episode_id=episode.id, agent_id=episode.agent_id)
        return episode.id

    async def retrieve(
        self,
        agent_id: str | None = None,
        task_id: str | None = None,
        since: datetime | None = None,
        min_importance: int = 5,
        limit: int = 100,
    ) -> list[Episode]:
        query = "SELECT * FROM episodes WHERE importance_score >= ?"
        params: list[Any] = [min_importance]

        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)
        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        return [
            Episode(
                id=row["id"],
                agent_id=row["agent_id"],
                task_id=row["task_id"],
                event_type=row["event_type"],
                content=row["content"],
                importance_score=row["importance_score"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    async def archive_old(self) -> int:
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        await self.db.execute(
            "DELETE FROM episodes WHERE created_at < ?",
            (cutoff.isoformat(),),
        )
        return 0
