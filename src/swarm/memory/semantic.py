import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import structlog

try:
    import chromadb

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from swarm.db.connection import Database

logger = structlog.get_logger()


@dataclass
class SemanticEntry:
    id: str
    content: str
    embedding: list[float] | None = None
    created_by_agent: str | None = None
    task_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class SemanticMemory:
    def __init__(
        self,
        db: Database,
        chroma_path: str = "./data/chroma_db",
        embedding_model: str = "nomic-embed-text:latest",
        top_k: int = 10,
    ):
        self.db = db
        self.chroma_path = chroma_path
        self.embedding_model = embedding_model
        self.top_k = top_k
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        if not CHROMA_AVAILABLE:
            logger.warning("chromadb not available, semantic memory using SQLite fallback")
            return

        import os

        os.makedirs(self.chroma_path, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.chroma_path)
        self._collection = self._client.get_or_create_collection(
            name="semantic_memory",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("semantic_memory_initialized", chroma_path=self.chroma_path)

    async def store(
        self,
        entry: SemanticEntry,
        embedding: list[float] | None = None,
    ) -> str:
        if not entry.id:
            entry.id = str(uuid.uuid4())

        await self.db.execute(
            """INSERT INTO semantic_memory 
               (id, content, embedding, created_by_agent, task_id, tags, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.content,
                json.dumps(embedding) if embedding else None,
                entry.created_by_agent,
                entry.task_id,
                json.dumps(entry.tags),
                json.dumps(entry.metadata),
                entry.created_at.isoformat(),
            ),
        )

        if self._collection and embedding:
            self._collection.add(
                ids=[entry.id],
                documents=[entry.content],
                embeddings=[embedding],
                metadatas=[
                    {
                        "created_by_agent": entry.created_by_agent or "",
                        "tags": ",".join(entry.tags),
                        "task_id": entry.task_id or "",
                    }
                ],
            )

        logger.debug("semantic_entry_stored", entry_id=entry.id)
        return entry.id

    async def retrieve(
        self,
        query_embedding: list[float] | None = None,
        query_text: str | None = None,
        top_k: int | None = None,
        filter_tags: list[str] | None = None,
        filter_agents: list[str] | None = None,
    ) -> list[SemanticEntry]:
        if not self._collection or not (query_embedding or query_text):
            return []

        top_k = top_k or self.top_k

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding] if query_embedding else None,
                query_texts=[query_text] if query_text else None,
                n_results=top_k,
                where=self._build_filter(filter_tags, filter_agents),
            )

            entries = []
            if results and results["ids"]:
                for i, entry_id in enumerate(results["ids"][0]):
                    entries.append(
                        SemanticEntry(
                            id=entry_id,
                            content=results["documents"][0][i],
                            tags=(
                                results["metadatas"][0][i].get("tags", "").split(",")
                                if results["metadatas"][0][i].get("tags")
                                else []
                            ),
                            metadata={},
                        )
                    )
            return entries

        except Exception as e:
            logger.error("semantic_retrieval_error", error=str(e))
            return []

    def _build_filter(
        self, tags: list[str] | None, agents: list[str] | None
    ) -> dict | None:
        conditions = []
        if tags:
            for tag in tags:
                conditions.append({"tags": {"$contains": tag}})
        if agents:
            for agent in agents:
                conditions.append({"created_by_agent": agent})
        if len(conditions) == 1:
            return conditions[0]
        if len(conditions) > 1:
            return {"$and": conditions}
        return None
