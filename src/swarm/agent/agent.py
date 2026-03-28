import asyncio
import uuid
import time
from dataclasses import dataclass
from typing import Any
import structlog

from swarm.types.task import Task, AgentState
from swarm.types.result import TaskResult
from swarm.types.message import AgentMessage
from swarm.bus.message_bus import MessageBus
from swarm.memory.manager import MemoryManager
from swarm.llm.ollama_client import OllamaClient
from swarm.tools.base import Tool, ToolCall, ToolResult
from swarm.agent.strategies.chain_of_thought import (
    ReasoningStrategy,
    ReasoningResult,
    ChainOfThought,
)
from swarm.agent.strategies.tree_of_thought import TreeOfThought
from swarm.agent.strategies.react import ReAct
from swarm.agent.strategies.plan_and_execute import PlanAndExecute

logger = structlog.get_logger()


STRATEGY_MAP = {
    "CoT": ChainOfThought,
    "ToT": TreeOfThought,
    "ReAct": ReAct,
    "PlanAndExecute": PlanAndExecute,
}


@dataclass
class AgentConfig:
    name: str
    role: str
    model: str
    system_prompt: str
    strategy: str = "ReAct"
    tools: list[str] | None = None
    max_retries: int = 3
    timeout_seconds: int = 120


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        llm: OllamaClient,
        memory: MemoryManager,
        message_bus: MessageBus,
        tool_registry: dict[str, Tool] | None = None,
    ):
        self.config = config
        self.name = config.name
        self.role = config.role
        self.model = config.model
        self.system_prompt = config.system_prompt
        self.llm = llm
        self.memory = memory
        self.bus = message_bus
        self.tool_registry = tool_registry or {}

        strategy_class = STRATEGY_MAP.get(config.strategy, ReAct)
        self.strategy: ReasoningStrategy = strategy_class()

        self.state = AgentState.IDLE
        self.task_history: list[TaskResult] = []
        self.reasoning_traces: list[list[str]] = []

        self._subscription_id: str | None = None
        self._current_task_id: str | None = None
        self._retry_count = 0

    async def start(self) -> None:
        topics = [
            f"task.assigned.{self.name}",
            "task.assigned",
            "ping",
        ]

        async def handle_message(msg: AgentMessage) -> None:
            if msg.topic == "task.assigned" and msg.payload.get("assigned_agent") == self.name:
                await self.run(msg.payload.get("task"))
            elif msg.topic == "ping":
                await self.bus.send_direct(
                    self.name,
                    msg.sender,
                    {"pong": True, "agent": self.name},
                )

        self._subscription_id = await self.bus.subscribe(self.name, topics, handle_message)
        self.state = AgentState.IDLE
        logger.info("agent_started", agent=self.name, role=self.role)

    async def stop(self) -> None:
        if self._subscription_id:
            await self.bus.unsubscribe(self._subscription_id)
        logger.info("agent_stopped", agent=self.name)

    async def run(self, task: Task | dict) -> TaskResult:
        if isinstance(task, dict):
            task = Task(
                id=task.get("id", str(uuid.uuid4())),
                description=task.get("description", ""),
            )

        self._current_task_id = task.id
        self.state = AgentState.RUNNING

        start_time = time.time()
        result = TaskResult(task_id=task.id, success=False)

        try:
            await self.memory.store_episode(
                agent_id=self.name,
                task_id=task.id,
                event_type="task_started",
                content=f"Agent {self.name} started task: {task.description}",
                importance_score=7,
            )

            full_prompt = self._build_prompt(task.description)
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": full_prompt},
            ]

            response = await self.llm.chat(messages, model=self.model, temperature=0.7, stream=False)

            await self.memory.store_episode(
                agent_id=self.name,
                task_id=task.id,
                event_type="task_completed",
                content=f"Agent {self.name} completed: {response[:500]}",
                importance_score=8,
            )

            result.success = True
            result.final_answer = response
            result.execution_time_seconds = time.time() - start_time
            self.state = AgentState.COMPLETED

            await self.bus.broadcast(
                self.name,
                "task.completed",
                {
                    "task_id": task.id,
                    "result": response,
                    "agent": self.name,
                    "execution_time": result.execution_time_seconds,
                },
            )

        except asyncio.TimeoutError:
            result.error = f"Task timed out after {self.config.timeout_seconds}s"
            self.state = AgentState.FAILED
            logger.error("agent_timeout", agent=self.name, task_id=task.id)

        except Exception as e:
            result.error = str(e)
            self.state = AgentState.FAILED
            logger.error("agent_error", agent=self.name, error=str(e))

            if self._retry_count < self.config.max_retries:
                self._retry_count += 1
                logger.info("agent_retry", agent=self.name, retry=self._retry_count)
                return await self.run(task)

            await self.bus.broadcast(
                self.name,
                "task.failed",
                {
                    "task_id": task.id,
                    "error": str(e),
                    "retry_count": self._retry_count,
                    "agent": self.name,
                },
            )

        self.task_history.append(result)
        return result

    def _build_prompt(self, task_description: str) -> str:
        context = task_description

        if hasattr(self.memory, "retrieve_semantic"):
            context += "\n\n[Relevant context from memory would be injected here]"

        return context

    async def think(self, prompt: str, **kwargs) -> ReasoningResult:
        return await self.strategy.think(
            self.llm,
            prompt,
            system=self.system_prompt,
            **kwargs,
        )

    async def act(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        results = []
        for tc in tool_calls:
            tool = self.tool_registry.get(tc.tool_name)
            if not tool:
                results.append(
                    ToolResult(
                        call_id=tc.call_id,
                        tool_name=tc.tool_name,
                        success=False,
                        error=f"Tool '{tc.tool_name}' not found",
                    )
                )
                continue

            try:
                result = await tool.execute(tc.arguments)
                results.append(result)
            except Exception as e:
                results.append(
                    ToolResult(
                        call_id=tc.call_id,
                        tool_name=tc.tool_name,
                        success=False,
                        error=str(e),
                    )
                )

        return results

    async def reflect(self, result: TaskResult) -> str:
        reflection_prompt = f"""Reflect on this task result:

Task: {result.task_id}
Success: {result.success}
Result: {result.final_answer}
Error: {result.error}

What went well? What could be improved? Provide 1-2 specific insights."""

        messages = [
            {"role": "system", "content": "You are a reflective AI agent. Analyze task results concisely."},
            {"role": "user", "content": reflection_prompt},
        ]

        reflection = await self.llm.chat(messages, model=self.model, temperature=0.5, stream=False)

        await self.memory.store_semantic(
            content=reflection,
            created_by_agent=self.name,
            task_id=result.task_id,
            tags=["reflection", self.role],
        )

        return reflection

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        await self.bus.broadcast(self.name, topic, payload)

    @property
    def is_idle(self) -> bool:
        return self.state == AgentState.IDLE

    @property
    def is_running(self) -> bool:
        return self.state == AgentState.RUNNING
