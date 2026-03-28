#!/usr/bin/env python3
"""CLI entry point for the yconic-agent-swarm."""
import asyncio
import argparse
import sys
import structlog
from pathlib import Path

from swarm.orchestrator import SwarmOrchestrator
from swarm.types.task import TaskType

logger = structlog.get_logger()


async def run_task(orchestrator: SwarmOrchestrator, description: str, task_type: str = "general") -> None:
    task_type_map = {
        "code": TaskType.CODE,
        "research": TaskType.RESEARCH,
        "analysis": TaskType.ANALYSIS,
        "creative": TaskType.CREATIVE,
        "general": TaskType.GENERAL,
    }

    tt = task_type_map.get(task_type, TaskType.GENERAL)
    task_id = await orchestrator.receive_task(description, tt)

    print(f"Task submitted: {task_id}")
    print("Executing...")

    result = await orchestrator.execute(task_id)

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(result.final_answer or result.error or "No output")
    print("=" * 60)

    if result.artifacts:
        print("\nArtifacts:")
        for key, value in result.artifacts.items():
            print(f"  {key}: {value}")

    print(f"\nExecution time: {result.execution_time_seconds:.2f}s")
    print(f"Success: {result.success}")


async def list_agents(orchestrator: SwarmOrchestrator) -> None:
    print("Available agents:")
    for name, agent in orchestrator.agents.items():
        print(f"  - {name} ({agent.role})")
        print(f"    Strategy: {agent.config.strategy}")
        print(f"    Tools: {', '.join(agent.config.tools or [])}")
        print()


async def interactive_mode(orchestrator: SwarmOrchestrator) -> None:
    print("Interactive mode. Type 'exit' or 'quit' to stop.")
    print("Commands: /agents, /memory <query>, /exit")

    while True:
        try:
            prompt = input("\n> ").strip()
            if not prompt:
                continue

            if prompt.lower() in ("exit", "quit"):
                break

            if prompt.startswith("/agents"):
                await list_agents(orchestrator)
            elif prompt.startswith("/memory"):
                query = prompt[8:].strip()
                results = await orchestrator.memory.retrieve_semantic(query, top_k=5)
                print("Memory results:")
                for r in results:
                    print(f"  - {r.content[:200]}...")
            else:
                await run_task(orchestrator, prompt)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


async def main_async(args) -> None:
    config_path = args.config or "./config/agents.yaml"

    if not Path(config_path).exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    orchestrator = SwarmOrchestrator.from_config(config_path)
    await orchestrator.initialize()

    try:
        if args.agents:
            await list_agents(orchestrator)
        elif args.interactive:
            await interactive_mode(orchestrator)
        elif args.task:
            await run_task(orchestrator, args.task, args.task_type)
        else:
            print("No action specified. Use --task or --interactive")
            sys.exit(1)
    finally:
        await orchestrator.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="yconic-agent-swarm CLI")
    parser.add_argument("--config", "-c", default="./config/agents.yaml", help="Path to config file")
    parser.add_argument("--task", "-t", help="Task description")
    parser.add_argument("--task-type", default="general", choices=["code", "research", "analysis", "creative", "general"])
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--agents", action="store_true", help="List available agents")

    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    asyncio.run(main_async(args))


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    main()
