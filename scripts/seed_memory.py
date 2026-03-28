#!/usr/bin/env python3
"""Seed the memory system with initial knowledge and skills."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swarm.db.connection import Database
from swarm.memory.manager import MemoryManager


SEED_SKILLS = [
    {
        "skill_name": "code_generation",
        "description": "Generate clean, tested Python code",
        "prompt_template": "Write a {function_name} function that {description}. Include type hints and docstrings.",
        "success_rate": 0.75,
        "use_count": 10,
    },
    {
        "skill_name": "test_writing",
        "description": "Write pytest unit tests",
        "prompt_template": "Write pytest tests for {function_name}. Cover happy path and edge cases.",
        "success_rate": 0.8,
        "use_count": 8,
    },
    {
        "skill_name": "code_review",
        "description": "Review code for bugs and quality issues",
        "prompt_template": "Review this code for correctness, security, and style. Be specific about line numbers.",
        "success_rate": 0.85,
        "use_count": 5,
    },
    {
        "skill_name": "web_research",
        "description": "Research topics via web search",
        "prompt_template": "Search for {topic}. Find at least 3 credible sources and assess confidence levels.",
        "success_rate": 0.9,
        "use_count": 12,
    },
    {
        "skill_name": "task_planning",
        "description": "Decompose complex tasks into subtasks",
        "prompt_template": "Break down '{task}' into 3-8 atomic subtasks with dependencies.",
        "success_rate": 0.7,
        "use_count": 6,
    },
]

SEED_KNOWLEDGE = [
    {
        "content": "Python type hints improve code readability and catch bugs at development time",
        "category": "rule",
        "confidence": 0.95,
        "source_agent": "system",
    },
    {
        "content": "Always write tests BEFORE implementation when doing TDD",
        "category": "pattern",
        "confidence": 0.9,
        "source_agent": "system",
    },
    {
        "content": "In ReAct strategy, always extract tool calls before final answer",
        "category": "pattern",
        "confidence": 0.85,
        "source_agent": "system",
    },
    {
        "content": "Chain-of-Thought works best for straightforward, linear reasoning tasks",
        "category": "strategy",
        "confidence": 0.8,
        "source_agent": "system",
    },
    {
        "content": "Plan-and-Execute is best for complex multi-step workflows",
        "category": "strategy",
        "confidence": 0.8,
        "source_agent": "system",
    },
    {
        "content": "Memory consolidation should run periodically to prevent forgetting",
        "category": "rule",
        "confidence": 0.75,
        "source_agent": "system",
    },
    {
        "content": "Reviewer agent should always provide specific line numbers for issues",
        "category": "rule",
        "confidence": 0.9,
        "source_agent": "system",
    },
]


async def seed_memory():
    db = Database("./data/swarm.db")
    await db.initialize()

    memory = MemoryManager(db=db, chroma_path="./data/chroma_db")
    await memory.initialize()

    print("Seeding skills...")
    for skill in SEED_SKILLS:
        await memory.store_skill(**skill)
        print(f"  - {skill['skill_name']}")

    print("Seeding knowledge...")
    for knowledge in SEED_KNOWLEDGE:
        await memory.store_knowledge(**knowledge)
        print(f"  - {knowledge['category']}: {knowledge['content'][:60]}...")

    print("\nMemory seeded successfully!")

    await memory.stop_consolidation()
    await db.close()


if __name__ == "__main__":
    asyncio.run(seed_memory())
