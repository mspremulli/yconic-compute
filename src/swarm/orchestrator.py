import asyncio
import json
import re
import uuid
import time
from datetime import datetime
import structlog
import yaml

from swarm.types.task import Task, TaskGraph, TaskStatus, TaskType
from swarm.types.result import TaskResult, ExecutionStatus
from swarm.bus.message_bus import MessageBus
from swarm.memory.manager import MemoryManager
from swarm.llm.ollama_client import OllamaClient
from swarm.agent.agent import Agent, AgentConfig
from swarm.tools.base import Tool

logger = structlog.get_logger()


class SwarmOrchestrator:
    def __init__(
        self,
        agent_configs: list[AgentConfig],
        memory_manager: MemoryManager,
        message_bus: MessageBus,
        max_concurrent_agents: int = 5,
        max_retries: int = 3,
        task_timeout_seconds: int = 300,
    ):
        self.memory = memory_manager
        self.bus = message_bus
        self.max_concurrent = max_concurrent_agents
        self.max_retries = max_retries
        self.task_timeout = task_timeout_seconds

        self.agents: dict[str, Agent] = {}
        self.active_tasks: dict[str, Task] = {}
        self.task_results: dict[str, TaskResult] = {}
        self.task_graphs: dict[str, TaskGraph] = {}

        self._llm = OllamaClient()
        self._running = False
        self._agent_configs = agent_configs
        self._tool_registry: dict[str, Tool] = {}

    @classmethod
    def from_config(cls, config_path: str) -> "SwarmOrchestrator":
        with open(config_path) as f:
            config = yaml.safe_load(f)

        swarm_config = config.get("swarm", {})
        agent_configs = [
            AgentConfig(
                name=a["name"],
                role=a["role"],
                model=a.get("model", swarm_config.get("default_model", "llama3.3:70b")),
                system_prompt=a.get("system_prompt", f"You are a {a['role']} agent."),
                strategy=a.get("strategy", "ReAct"),
                tools=a.get("tools", []),
                max_retries=a.get("max_retries", 3),
            )
            for a in config.get("agents", [])
        ]

        message_bus = MessageBus()
        from swarm.db.connection import Database
        db = Database("./data/swarm.db")
        memory_manager = MemoryManager(
            db=db,
            chroma_path="./data/chroma_db",
        )

        return cls(
            agent_configs=agent_configs,
            memory_manager=memory_manager,
            message_bus=message_bus,
            max_concurrent_agents=swarm_config.get("max_concurrent_agents", 5),
            max_retries=swarm_config.get("max_retries", 3),
            task_timeout_seconds=swarm_config.get("task_timeout_seconds", 300),
        )

    def register_tool(self, tool: Tool) -> None:
        self._tool_registry[tool.name] = tool
        logger.info("tool_registered", tool=tool.name)

    async def initialize(self) -> None:
        await self.memory.initialize()

        from swarm.tools.bash import BashTool, PythonReplTool, CalculatorTool
        from swarm.tools.file_system import ReadFileTool, WriteFileTool
        from swarm.tools.memory_tools import register_memory_tools

        self.register_tool(BashTool(timeout_seconds=60))
        self.register_tool(PythonReplTool(timeout_seconds=30))
        self.register_tool(CalculatorTool())
        self.register_tool(ReadFileTool())
        self.register_tool(WriteFileTool())

        memory_tools = register_memory_tools(self.memory)
        for name, tool in memory_tools.items():
            self.register_tool(tool)

        for cfg in self._agent_configs:
            available_tools = {name: self._tool_registry[name] for name in (cfg.tools or []) if name in self._tool_registry}
            agent = Agent(
                config=cfg,
                llm=self._llm,
                memory=self.memory,
                message_bus=self.bus,
                tool_registry=available_tools,
            )
            self.agents[cfg.name] = agent
            await agent.start()

        await self.bus.subscribe("orchestrator", ["task.completed", "task.failed"], self._handle_agent_result)

        self._running = True
        logger.info("orchestrator_initialized", agents=list(self.agents.keys()))

    async def shutdown(self) -> None:
        self._running = False
        for agent in self.agents.values():
            await agent.stop()
        await self._llm.close()
        logger.info("orchestrator_shutdown")

    async def receive_task(self, description: str, task_type: TaskType = TaskType.GENERAL) -> str:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            description=description,
            task_type=task_type,
            created_at=datetime.utcnow(),
        )

        self.active_tasks[task_id] = task

        await self.memory.store_episode(
            agent_id="orchestrator",
            task_id=task_id,
            event_type="task_received",
            content=f"Task received: {description}",
            importance_score=8,
        )

        logger.info("task_received", task_id=task_id, description=description[:100])
        return task_id

    async def execute(self, task_id: str) -> TaskResult:
        if task_id not in self.active_tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.active_tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()

        start_time = time.time()

        try:
            task_graph = await self._plan(task)
            self.task_graphs[task_id] = task_graph

            result = await self._execute_graph(task_graph)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result.final_answer

            result.execution_time_seconds = time.time() - start_time
            self.task_results[task_id] = result

            logger.info("task_completed", task_id=task_id, duration=result.execution_time_seconds)
            return result

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()

            result = TaskResult(task_id=task_id, success=False, error=str(e))
            result.execution_time_seconds = time.time() - start_time
            self.task_results[task_id] = result

            logger.error("task_failed", task_id=task_id, error=str(e))
            return result

    async def _plan(self, task: Task) -> TaskGraph:
        planner = self.agents.get("planner")
        if not planner:
            graph = TaskGraph()
            graph.add_task(task)
            return graph

        planning_prompt = f"""Decompose this task into atomic subtasks:

Task: {task.description}
Task Type: {task.task_type.value}

Available agents: {list(self.agents.keys())}

Return a JSON object with:
{{
  "tasks": [
    {{"id": "sub1", "description": "...", "assigned_agent": "agent_name", "priority": 1}}
  ],
  "edges": [["sub1", "sub2"]]  # prerequisite -> dependent
}}"""

        messages = [
            {"role": "system", "content": "You are a planner. Return ONLY valid JSON."},
            {"role": "user", "content": planning_prompt},
        ]

        try:
            response = await self._llm.chat(messages, model=planner.model, temperature=0.3, stream=False)

            if isinstance(response, str):
                text = response.strip()
            elif hasattr(response, "__anext__"):
                chunks = []
                async for chunk in response:
                    chunks.append(chunk)
                text = "".join(chunks).strip()
            else:
                text = str(response).strip()

            if not text:
                raise ValueError("Empty response from planner")

            plan_data = None

            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group(1).strip())

            if plan_data is None:
                plan_data = json.loads(text)

        except Exception as e:
            logger.warning("planning_failed", error=str(e))
            plan_data = {
                "tasks": [{"id": task.id, "description": task.description, "assigned_agent": "coder", "priority": 1}],
                "edges": [],
            }

        graph = TaskGraph()

        for t_data in plan_data.get("tasks", [{"id": task.id, "description": task.description, "assigned_agent": "coder", "priority": 1}]):
            sub_task = Task(
                id=t_data.get("id", str(uuid.uuid4())),
                description=t_data.get("description", ""),
                assigned_agent=t_data.get("assigned_agent"),
                priority=t_data.get("priority", 0),
            )
            graph.add_task(sub_task)

        for edge in plan_data.get("edges", []):
            if len(edge) == 2:
                graph.add_edge(edge[0], edge[1])

        logger.info("task_planned", task_id=task.id, subtasks=len(graph.tasks))
        return graph

    async def _execute_graph(self, graph: TaskGraph) -> TaskResult:
        agent_traces: dict[str, list[str]] = {}
        all_results = {}

        while not graph.is_complete():
            ready_tasks = graph.get_ready_tasks()
            
            if not ready_tasks:
                break

            for task in ready_tasks:
                agent_name = task.assigned_agent or self._assign_agent(task)

                if agent_name not in self.agents:
                    task.status = TaskStatus.FAILED
                    task.error = f"Agent {agent_name} not found"
                    graph.mark_complete(task.id)
                    continue

                agent = self.agents[agent_name]
                await self._dispatch_task(task, agent, graph, all_results, agent_traces)

        return self._aggregate_results(graph, agent_traces)

    async def _dispatch_task(
        self,
        task: Task,
        agent: Agent,
        graph: TaskGraph,
        results: dict,
        traces: dict[str, list[str]],
    ) -> None:
        try:
            result = await asyncio.wait_for(
                agent.run(task),
                timeout=self.task_timeout,
            )
            results[task.id] = result
            self.task_results[task.id] = result  # Store for aggregation
            graph.mark_complete(task.id)

            await self.memory.store_episode(
                agent_id=agent.name,
                task_id=task.id,
                event_type="task_completed",
                content=result.final_answer or result.error or "",
                importance_score=7,
            )

        except asyncio.TimeoutError:
            results[task.id] = TaskResult(task_id=task.id, success=False, error="Task timeout")
            self.task_results[task.id] = results[task.id]
            task.status = TaskStatus.FAILED
            task.error = "Task timeout"
            graph.tasks[task.id].status = TaskStatus.FAILED

        except Exception as e:
            results[task.id] = TaskResult(task_id=task.id, success=False, error=str(e))
            self.task_results[task.id] = results[task.id]
            task.status = TaskStatus.FAILED
            task.error = str(e)
            graph.tasks[task.id].status = TaskStatus.FAILED

    def _assign_agent(self, task: Task) -> str:
        if task.task_type == TaskType.CODE:
            return "coder"
        elif task.task_type == TaskType.RESEARCH:
            return "researcher"
        return "coder"

    async def _handle_agent_result(self, msg) -> None:
        pass

    def _aggregate_results(self, graph: TaskGraph, traces: dict[str, list[str]]) -> TaskResult:
        successful = all(t.status == TaskStatus.COMPLETED for t in graph.tasks.values())
        outputs = {tid: self.task_results.get(tid) for tid in graph.tasks}

        final_answer = "\n\n".join(
            f"[{tid}] {r.final_answer or r.error}"
            for tid, r in outputs.items()
            if r
        )

        return TaskResult(
            task_id=list(graph.tasks.keys())[0] if graph.tasks else "",
            success=successful,
            final_answer=final_answer,
            agent_traces=traces,
        )

    async def get_status(self, task_id: str) -> ExecutionStatus:
        graph = self.task_graphs.get(task_id)
        if not graph:
            return ExecutionStatus(
                task_id=task_id,
                status="unknown",
                completed_tasks=0,
                total_tasks=0,
                running_agents=[],
                failed_tasks=[],
                progress_percent=0.0,
            )

        completed = sum(1 for t in graph.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = [tid for tid, t in graph.tasks.items() if t.status == TaskStatus.FAILED]
        running = [t.assigned_agent for t in graph.tasks.values() if t.status == TaskStatus.RUNNING and t.assigned_agent]

        return ExecutionStatus(
            task_id=task_id,
            status="running" if running else ("complete" if graph.is_complete() else "unknown"),
            completed_tasks=completed,
            total_tasks=len(graph.tasks),
            running_agents=running,
            failed_tasks=failed,
            progress_percent=(completed / len(graph.tasks) * 100) if graph.tasks else 0,
        )

    async def cancel(self, task_id: str) -> None:
        if task_id in self.active_tasks:
            self.active_tasks[task_id].status = TaskStatus.CANCELLED
            logger.info("task_cancelled", task_id=task_id)
