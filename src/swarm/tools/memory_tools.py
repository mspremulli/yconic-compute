import uuid
from typing import Any
import structlog

from swarm.tools.base import Tool, ToolResult
from swarm.memory.manager import MemoryManager

logger = structlog.get_logger()


class VectorSearchTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "vector_search"
        self.description = "Search semantic memory for relevant facts and context"
        self.input_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Number of results", "default": 5},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
            },
            "required": ["query"],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            results = await self.memory.retrieve_semantic(
                query=arguments["query"],
                top_k=arguments.get("top_k", 5),
                filter_tags=arguments.get("tags"),
            )

            output = "\n\n".join(
                f"[{i+1}] {r.content[:300]}..."
                + (f" (tags: {', '.join(r.tags)})" if r.tags else "")
                for i, r in enumerate(results)
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output or "No results found.",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class MemoryRetrieveEpisodesTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "memory_retrieve_episodes"
        self.description = "Retrieve past agent actions and events from episodic memory"
        self.input_schema = {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Filter by agent"},
                "task_id": {"type": "string", "description": "Filter by task"},
                "min_importance": {"type": "integer", "default": 5},
            },
            "required": [],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            episodes = await self.memory.retrieve_episodes(
                agent_id=arguments.get("agent_id"),
                task_id=arguments.get("task_id"),
                min_importance=arguments.get("min_importance", 5),
            )

            output = "\n\n".join(
                f"[{e.agent_id}] {e.event_type}: {e.content[:200]}..."
                for e in episodes
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output or "No episodes found.",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class MemoryStoreTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "memory_store"
        self.description = "Store information in semantic memory"
        self.input_schema = {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to store"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "task_id": {"type": "string"},
            },
            "required": ["content"],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            await self.memory.store_semantic(
                content=arguments["content"],
                created_by_agent="system",
                task_id=arguments.get("task_id"),
                tags=arguments.get("tags", []),
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output="Stored in semantic memory.",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class MemoryStoreSkillTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "memory_store_skill"
        self.description = "Store or update a learned skill pattern"
        self.input_schema = {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string"},
                "prompt_template": {"type": "string"},
                "description": {"type": "string"},
                "success_rate": {"type": "number"},
                "use_count": {"type": "integer"},
            },
            "required": ["skill_name", "prompt_template"],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            await self.memory.store_skill(
                skill_name=arguments["skill_name"],
                prompt_template=arguments["prompt_template"],
                description=arguments.get("description"),
                success_rate=arguments.get("success_rate", 0.0),
                use_count=arguments.get("use_count", 0),
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=f"Skill '{arguments['skill_name']}' stored.",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class MemoryStoreKnowledgeTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "memory_store_knowledge"
        self.description = "Store verified knowledge in long-term memory"
        self.input_schema = {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "category": {"type": "string"},
                "confidence": {"type": "number"},
                "source_agent": {"type": "string"},
            },
            "required": ["content", "category", "confidence"],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            await self.memory.store_knowledge(
                content=arguments["content"],
                category=arguments["category"],
                confidence=arguments["confidence"],
                source_agent=arguments.get("source_agent", "system"),
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output="Knowledge stored in long-term memory.",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class MemoryConsolidateTool(Tool):
    def __init__(self, memory: MemoryManager):
        self.name = "memory_consolidate"
        self.description = "Run memory consolidation (moves high-value episodes to semantic memory)"
        self.input_schema = {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Consolidate for specific agent"},
            },
            "required": [],
        }
        self.memory = memory

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        call_id = str(uuid.uuid4())

        try:
            report = await self.memory.consolidate(
                agent_id=arguments.get("agent_id"),
            )

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=f"Consolidated: {report.episodes_promoted} promoted, {report.duration_ms:.1f}ms",
            )

        except Exception as e:
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                error=str(e),
            )


def register_memory_tools(memory: MemoryManager) -> dict[str, Tool]:
    return {
        "vector_search": VectorSearchTool(memory),
        "memory_retrieve_episodes": MemoryRetrieveEpisodesTool(memory),
        "memory_store": MemoryStoreTool(memory),
        "memory_store_skill": MemoryStoreSkillTool(memory),
        "memory_store_knowledge": MemoryStoreKnowledgeTool(memory),
        "memory_consolidate": MemoryConsolidateTool(memory),
    }
