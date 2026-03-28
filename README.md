# yconic-agent-swarm

On-Device Autonomous Agent Swarm — multi-agent AI system with shared memory, A2A communication, and 5-layer memory stack. All running locally via Ollama.

## Features

- **6 Specialized Agents**: planner, coder, researcher, reviewer, synthesizer, meta_learner
- **4 Reasoning Strategies**: Chain-of-Thought, Tree-of-Thought, ReAct, Plan-and-Execute
- **5-Layer Memory Stack**: Working, Episodic, Semantic, Long-Term, Skill
- **A2A Message Bus**: In-process pub/sub with request/reply patterns
- **Tool System**: bash, python_repl, calculator, file ops, web search, memory
- **Full Audit Trail**: SQLite-backed logging of every agent action
- **Structured Logging**: JSON + console output via structlog

## Quick Start

```bash
# Install dependencies
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# Initialize database
PYTHONPATH=./src ./venv/bin/python scripts/init_db.py

# Seed memory with initial skills and knowledge
PYTHONPATH=./src ./venv/bin/python scripts/seed_memory.py

# Run a task
PYTHONPATH=./src ./venv/bin/python -m swarm.main -t "Build a REST API for a todo app" --task-type code

# Interactive mode
PYTHONPATH=./src ./venv/bin/python -m swarm.main --interactive

# List agents
PYTHONPATH=./src ./venv/bin/python -m swarm.main --agents
```

## Architecture

```
SwarmOrchestrator
    ├── Planner Agent (PlanAndExecute)
    ├── Coder Agent (ReAct)
    ├── Researcher Agent (ReAct)
    ├── Reviewer Agent (CoT)
    ├── Synthesizer Agent (ToT)
    └── Meta-Learner Agent (PlanAndExecute)

Shared Memory Stack:
├── Working (in-memory LRU)
├── Episodic (SQLite)
├── Semantic (ChromaDB)
├── Long-Term (SQLite)
└── Skill (SQLite)

A2A Message Bus (pub/sub):
├── task.assigned
├── task.completed
├── task.failed
├── code.generated
├── code.reviewed
└── research.findings
```

## Project Structure

```
src/swarm/
├── agent/          # Agent class and strategies
│   ├── agents/    # Specialized agent configs
│   └── strategies/# CoT, ToT, ReAct, PlanAndExecute
├── memory/        # 5-layer memory system
├── bus/           # A2A message bus
├── tools/         # Tool implementations
├── llm/           # Ollama client
├── db/            # SQLite schema
├── api/           # FastAPI REST server
├── types/         # Data classes
├── orchestrator.py
├── audit.py
└── main.py
```

## Configuration

Edit `config/agents.yaml` to:
- Change the model (`llama3.3:70b`, `llama3:8b`, etc.)
- Adjust agent tools and strategies
- Configure tool permissions (bash allowed commands, etc.)

## Requirements

- Python 3.11+
- Ollama running locally with a model loaded
- 16GB+ RAM recommended for 7B models, 64GB+ for 70B models

## License

MIT
