import uuid
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import structlog

from swarm.db.connection import Database
from swarm.memory.episodic import EpisodicMemory, Episode
from swarm.memory.semantic import SemanticMemory, SemanticEntry
from swarm.memory.long_term import LongTermMemory, Knowledge
from swarm.memory.skill import SkillMemory, Skill
from swarm.memory.working import WorkingMemory
from swarm.llm.ollama_client import OllamaClient

logger = structlog.get_logger()


@dataclass
class ConsolidationReport:
    episodes_processed: int = 0
    episodes_promoted: int = 0
    knowledge_promoted: int = 0
    duplicates_removed: int = 0
    duration_ms: float = 0.0


class MemoryManager:
    def __init__(
        self,
        db: Database,
        chroma_path: str = "./data/chroma_db",
        embedding_model: str = "nomic-embed-text:latest",
        ollama_client: OllamaClient | None = None,
    ):
        self.db = db
        self.ollama = ollama_client or OllamaClient()

        self.episodic = EpisodicMemory(db)
        self.semantic = SemanticMemory(db, chroma_path, embedding_model)
        self.long_term = LongTermMemory(db)
        self.skill = SkillMemory(db)
        self.working = WorkingMemory()

        self._consolidation_task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> None:
        await self.db.initialize()
        await self.semantic.initialize()
        self._running = True
        logger.info("memory_manager_initialized")

    async def start_consolidation(self, interval_hours: int = 24) -> None:
        async def _consolidation_loop():
            while self._running:
                await asyncio.sleep(interval_hours * 3600)
                try:
                    await self.consolidate(agent_id="system")
                except Exception as e:
                    logger.error("consolidation_error", error=str(e))

        self._consolidation_task = asyncio.create_task(_consolidation_loop())

    async def stop_consolidation(self) -> None:
        self._running = False
        if self._consolidation_task:
            self._consolidation_task.cancel()
            try:
                await self._consolidation_task
            except asyncio.CancelledError:
                pass

    async def store_episode(
        self,
        agent_id: str,
        task_id: str,
        event_type: str,
        content: str,
        importance_score: int = 5,
    ) -> str:
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            task_id=task_id,
            event_type=event_type,
            content=content,
            importance_score=importance_score,
        )
        await self.episodic.store(episode)
        return episode.id

    async def retrieve_episodes(
        self,
        agent_id: str | None = None,
        task_id: str | None = None,
        since: datetime | None = None,
        min_importance: int = 5,
    ) -> list[Episode]:
        return await self.episodic.retrieve(
            agent_id=agent_id,
            task_id=task_id,
            since=since,
            min_importance=min_importance,
        )

    async def store_semantic(
        self,
        content: str,
        created_by_agent: str,
        task_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        embedding = None
        try:
            embedding = await self.ollama.embed(content)
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))

        entry = SemanticEntry(
            id=str(uuid.uuid4()),
            content=content,
            created_by_agent=created_by_agent,
            task_id=task_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        await self.semantic.store(entry, embedding)
        return entry.id

    async def retrieve_semantic(
        self,
        query: str,
        top_k: int = 10,
        filter_tags: list[str] | None = None,
        filter_agents: list[str] | None = None,
    ) -> list[SemanticEntry]:
        embedding = None
        try:
            embedding = await self.ollama.embed(query)
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))

        return await self.semantic.retrieve(
            query_embedding=embedding,
            query_text=query,
            top_k=top_k,
            filter_tags=filter_tags,
            filter_agents=filter_agents,
        )

    async def store_knowledge(
        self,
        content: str,
        category: str,
        confidence: float,
        source_agent: str,
    ) -> str:
        knowledge = Knowledge(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            confidence=confidence,
            source_agent=source_agent,
        )
        await self.long_term.store(knowledge)
        return knowledge.id

    async def retrieve_knowledge(
        self,
        category: str | None = None,
        min_confidence: float = 0.7,
    ) -> list[Knowledge]:
        return await self.long_term.retrieve(
            category=category,
            min_confidence=min_confidence,
        )

    async def store_skill(
        self,
        skill_name: str,
        prompt_template: str,
        description: str | None = None,
        success_rate: float = 0.0,
        use_count: int = 0,
    ) -> str:
        skill = Skill(
            id=str(uuid.uuid4()),
            skill_name=skill_name,
            description=description,
            prompt_template=prompt_template,
            success_rate=success_rate,
            use_count=use_count,
        )
        await self.skill.store(skill)
        return skill.id

    async def retrieve_skills(
        self,
        skill_name: str | None = None,
        min_success_rate: float = 0.5,
    ) -> list[Skill]:
        return await self.skill.retrieve(
            skill_name=skill_name,
            min_success_rate=min_success_rate,
        )

    async def update_skill_success(
        self, skill_name: str, success: bool, updated_template: str | None = None
    ) -> None:
        await self.skill.update_success(skill_name, success, updated_template)

    async def consolidate(self, agent_id: str | None = None) -> ConsolidationReport:
        import time

        start = time.time()
        report = ConsolidationReport()

        high_importance = await self.episodic.retrieve(
            agent_id=agent_id,
            min_importance=8,
            limit=100,
        )
        report.episodes_processed = len(high_importance)

        for ep in high_importance:
            embedding = None
            try:
                embedding = await self.ollama.embed(ep.content)
            except Exception:
                pass

            await self.semantic.store(
                SemanticEntry(
                    id=str(uuid.uuid4()),
                    content=ep.content,
                    created_by_agent=ep.agent_id,
                    task_id=ep.task_id,
                    tags=["consolidated", ep.event_type],
                ),
                embedding,
            )
            report.episodes_promoted += 1

        await self.long_term.deduplicate()
        report.duration_ms = (time.time() - start) * 1000

        logger.info("consolidation_complete", report=report)
        return report
