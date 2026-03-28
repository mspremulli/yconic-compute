from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any
import structlog

from swarm.orchestrator import SwarmOrchestrator
from swarm.types.task import TaskType

logger = structlog.get_logger()

app = FastAPI(title="yconic-agent-swarm API")

_orchestrator: SwarmOrchestrator | None = None


class TaskRequest(BaseModel):
    description: str
    task_type: str = "general"


class TaskResponse(BaseModel):
    task_id: str
    status: str


def set_orchestrator(orch: SwarmOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orch


@app.post("/tasks", response_model=TaskResponse)
async def create_task(req: TaskRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    task_type_map = {
        "code": TaskType.CODE,
        "research": TaskType.RESEARCH,
        "analysis": TaskType.ANALYSIS,
        "creative": TaskType.CREATIVE,
        "general": TaskType.GENERAL,
    }

    tt = task_type_map.get(req.task_type, TaskType.GENERAL)
    task_id = await _orchestrator.receive_task(req.description, tt)

    background_tasks.add_task(_orchestrator.execute, task_id)

    return TaskResponse(task_id=task_id, status="pending")


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    status = await _orchestrator.get_status(task_id)

    return {
        "task_id": status.task_id,
        "status": status.status,
        "completed_tasks": status.completed_tasks,
        "total_tasks": status.total_tasks,
        "progress_percent": status.progress_percent,
        "running_agents": status.running_agents,
        "failed_tasks": status.failed_tasks,
    }


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> dict[str, Any]:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    if task_id not in _orchestrator.task_results:
        raise HTTPException(status_code=404, detail="Task result not found")

    result = _orchestrator.task_results[task_id]
    return result.to_dict()


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict[str, str]:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    await _orchestrator.cancel(task_id)
    return {"status": "cancelled"}


@app.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    return [
        {
            "name": name,
            "role": agent.role,
            "strategy": agent.config.strategy,
            "tools": agent.config.tools or [],
            "state": agent.state.value,
        }
        for name, agent in _orchestrator.agents.items()
    ]


@app.get("/memory/search")
async def search_memory(q: str, top_k: int = 10) -> list[dict[str, Any]]:
    if not _orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    results = await _orchestrator.memory.retrieve_semantic(query=q, top_k=top_k)

    return [
        {
            "id": r.id,
            "content": r.content,
            "tags": r.tags,
            "created_by": r.created_by_agent,
        }
        for r in results
    ]


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


async def start_server(orchestrator: SwarmOrchestrator, host: str = "0.0.0.0", port: int = 8080) -> None:
    set_orchestrator(orchestrator)

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
