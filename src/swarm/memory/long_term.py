import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import structlog

from swarm.db.connection import Database

logger = structlog.get_logger()


@dataclass
class Knowledge:
    id: str
    content: str
    category: str
    confidence: float
    source_agent: str
    verified: bool = False
    verified_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class LongTermMemory:
    def __init__(self, db: Database, min_confidence: float = 0.7):
        self.db = db
        self.min_confidence = min_confidence

    async def store(self, knowledge: Knowledge) -> str:
        if not knowledge.id:
            knowledge.id = str(uuid.uuid4())

        await self.db.execute(
            """INSERT INTO knowledge 
               (id, content, category, confidence, source_agent, verified, verified_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                knowledge.id,
                knowledge.content,
                knowledge.category,
                knowledge.confidence,
                knowledge.source_agent,
                1 if knowledge.verified else 0,
                knowledge.verified_at.isoformat() if knowledge.verified_at else None,
                knowledge.created_at.isoformat(),
                knowledge.updated_at.isoformat(),
            ),
        )

        logger.debug("knowledge_stored", knowledge_id=knowledge.id, category=knowledge.category)
        return knowledge.id

    async def retrieve(
        self,
        category: str | None = None,
        min_confidence: float | None = None,
        verified_only: bool = False,
        limit: int = 100,
    ) -> list[Knowledge]:
        query = "SELECT * FROM knowledge WHERE 1=1"
        params: list[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category)

        threshold = min_confidence or self.min_confidence
        query += " AND confidence >= ?"
        params.append(threshold)

        if verified_only:
            query += " AND verified = 1"

        query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.fetch_all(query, tuple(params))
        return [
            Knowledge(
                id=row["id"],
                content=row["content"],
                category=row["category"],
                confidence=row["confidence"],
                source_agent=row["source_agent"],
                verified=bool(row["verified"]),
                verified_at=datetime.fromisoformat(row["verified_at"]) if row["verified_at"] else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    async def verify(self, knowledge_id: str) -> None:
        await self.db.execute(
            """UPDATE knowledge 
               SET verified = 1, verified_at = ?, updated_at = ?
               WHERE id = ?""",
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), knowledge_id),
        )

    async def deduplicate(self, similarity_threshold: float = 0.85) -> int:
        logger.info("deduplication_started", threshold=similarity_threshold)
        return 0
