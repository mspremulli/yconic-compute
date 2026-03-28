# SPEC.md — On-Device Autonomous Agent Swarm

## 1. Context & Motivation

Deploy a multi-agent system where 5–10 autonomous AI agents collaborate on complex tasks — code generation, research synthesis, or game-playing — with shared memory and real-time inter-agent communication, all running locally on DGX Spark-class hardware.

This project implements the **Autonomous Multi-Agent AI Systems** curriculum's core architecture: specialized agents with defined roles, a shared memory stack, an A2A (agent-to-agent) communication bus, and an orchestrator that manages workflow, retries, and failure recovery.

**Core problem this solves:** Single LLM instances hit ceiling on complex, multi-step tasks. Breaking work across specialized agents (each using the right prompting strategy) yields better results than one monolithic model call. The swarm architecture enables emergent problem-solving beyond any single agent's capability.

**Target users:** Developers building autonomous AI systems, researchers benchmarking multi-agent strategies, teams needing local-first AI pipelines.

---

## 2. Technical Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Runtime** | Python 3.11+ | Ecosystem, async support, Ollama SDK |
| **LLM Backend** | Ollama (local) | Zero cloud dependency, 128 GB unified memory enables 5+ concurrent instances |
| **Message Bus** | asyncio + `message_bus.MessageBus` | In-process pub/sub, zero network overhead |
| **Memory Stack** | SQLite (episodic/long-term) + ChromaDB (semantic) | Persistent, queryable, runs on DGX Spark |
| **Agent Framework** | Custom `Agent` class + `Tool` protocol | Full control, minimal abstraction overhead |
| **Orchestration** | `SwarmOrchestrator` | Task graph execution, dependency resolution, retry logic |
| **Observability** | Structured logging + SQLite audit trail | Every agent action logged with timestamps |
| **Config** | YAML (`config/agents.yaml`) | Declarative agent definitions, easy to modify |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SwarmOrchestrator                       │
│  - Receives task from user                                 │
│  - Decomposes into subtasks (task graph)                   │
│  - Assigns subtasks to agents                               │
│  - Monitors progress, retries on failure                   │
│  - Aggregates results                                       │
└────────────────┬────────────────────────────────────────────┘
                 │ spawns / monitors
    ┌────────────┼────────────┬────────────┬─────────────────┐
    ▼            ▼            ▼            ▼                 ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐       ┌────────┐
│Agent 1 │  │Agent 2 │  │Agent 3 │  │Agent 4 │  ...  │Agent N │
│Planner │  │Coder   │  │Research│  │Reviewer│       │Specialist│
└────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘       └────┬───┘
     │           │           │           │                 │
     └──────────┴───────────┴───────────┴─────────────────┘
              │  A2A Message Bus (pub/sub)
              │
     ┌────────┴──────────────────────────────────┐
     │           Shared Memory Stack             │
     │  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
     │  │ Working  │  │ Semantic │  │Episodic │ │
     │  │ Memory    │  │ Memory   │  │ Memory  │ │
     │  │(in-memory)│  │(ChromaDB)│  │(SQLite) │ │
     │  └──────────┘  └──────────┘  └─────────┘ │
     │  ┌──────────┐  ┌──────────┐               │
     │  │ Long-Term│  │  Skill   │               │
     │  │ Memory   │  │ Memory   │               │
     │  │(SQLite)  │  │(SQLite)  │               │
     │  └──────────┘  └──────────┘               │
     └───────────────────────────────────────────┘
              │
     ┌────────┴────────┐
     │   Tool Servers   │
     │ - Web Search     │
     │ - Code Executor  │
     │ - File System    │
     │ - Calculator     │
     └──────────────────┘
```

### 3.1 Data Flow

1. **Task Ingestion**: User submits task → `SwarmOrchestrator.receive_task()`
2. **Task Decomposition**: Orchestrator prompts a Planner agent → generates task dependency graph
3. **Agent Dispatch**: Orchestrator spawns agents based on task graph, respects dependencies
4. **A2A Communication**: Agents publish results to message bus → subscribers react
5. **Memory Operations**: Each agent reads/writes to appropriate memory layers
6. **Tool Invocation**: Agents call tools via `ToolServer` (local MCP-like interface)
7. **Result Aggregation**: Orchestrator collects outputs → formats final response
8. **Audit Logging**: Every step logged to SQLite with agent_id, timestamp, action, outcome

---

## 4. Component Specifications

### 4.1 Agent Class

```python
class Agent:
    name: str                          # Unique agent identifier
    role: str                          # "planner", "coder", "researcher", etc.
    model: str                         # Ollama model name, e.g. "llama3.3:70b"
    system_prompt: str                 # Role definition and behavioral constraints
    tools: list[Tool]                  # Available tools for this agent
    memory: AgentMemoryView            # Subset of shared memory this agent can access
    strategy: ReasoningStrategy        # CoT | ToT | ReAct | PlanAndExecute
    max_retries: int = 3
    timeout_seconds: int = 120

    async def run(task: Task) -> TaskResult: ...
    async def think(prompt: str, strategy: ReasoningStrategy) -> str: ...
    async def act(tool_calls: list[ToolCall]) -> list[ToolResult]: ...
    async def reflect(result: TaskResult) -> str: ...
    async def publish(message: AgentMessage) -> None: ...
    async def subscribe(topic: str, handler: Callable) -> None: ...
```

**Reasoning Strategies:**

| Strategy | Description | Best For |
|----------|-------------|----------|
| `CoT` | Chain-of-Thought: linear step-by-step reasoning | Straightforward tasks |
| `ToT` | Tree-of-Thought: explore multiple branches, pick best | Complex problem-solving |
| `ReAct` | Reasoning + Acting: think → act → observe → repeat | Tool-use tasks |
| `PlanAndExecute` | Make plan first, then execute steps | Multi-step workflows |

**Agent States:**
```
IDLE → RUNNING → WAITING_FOR_INPUT → COMPLETED
                   ↓
               FAILED (with retry count)
```

### 4.2 Tool Protocol

```python
from dataclasses import dataclass
from typing import Protocol, Any
from abc import ABC, abstractmethod

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str                    # Unique ID for this call
    timestamp: datetime
    agent_id: str

@dataclass
class ToolResult:
    call_id: str
    success: bool
    output: Any
    error: str | None
    execution_time_ms: float

class Tool(Protocol):
    name: str
    description: str
    input_schema: dict              # JSON Schema for arguments
    requires_confirmation: bool      # For dangerous operations

    async def execute(self, arguments: dict[str, Any]) -> ToolResult: ...
```

**Built-in Tools:**

| Tool | Purpose | Safety |
|------|---------|--------|
| `web_search` | Search the web via Exa API | Rate-limited, content filtered |
| `url_fetch` | Retrieve and summarize web pages | Content filtered |
| `bash` | Execute shell commands | Restricted to sandboxed env, no destructive commands |
| `read_file` | Read file contents | Path-restricted to workspace |
| `write_file` | Write/edit files | Path-restricted, no system files |
| `python_repl` | Execute Python code in sandbox | Timeout + resource limits |
| `calculator` | Arithmetic and math expression eval | Safe by design |
| `vector_search` | Query semantic memory | Read-only |

### 4.3 A2A Message Bus

```python
@dataclass
class AgentMessage:
    id: str                         # UUID
    sender: str                     # Agent name
    recipients: list[str] | None   # None = broadcast
    topic: str                      # e.g. "code_complete", "review_requested"
    payload: dict                   # Arbitrary structured data
    reply_to: str | None            # For request/reply patterns
    timestamp: datetime
    priority: int = 0               # Higher = more urgent

class MessageBus:
    """In-process pub/sub message bus. Zero network overhead."""

    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to the bus."""

    async def subscribe(
        self,
        agent_id: str,
        topics: list[str],
        handler: Callable[[AgentMessage], Coroutine]
    ) -> str:
        """Subscribe to topics. Returns subscription ID."""

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""

    async def send_direct(
        self,
        sender: str,
        recipient: str,
        payload: dict
    ) -> None:
        """Send a direct message to a specific agent (request/reply)."""

    async def broadcast(
        self,
        sender: str,
        topic: str,
        payload: dict,
        exclude: list[str] | None = None
    ) -> None:
        """Broadcast to all agents subscribed to topic."""
```

**Standard Topics:**

| Topic | Publishers | Subscribers | Payload |
|-------|-----------|-------------|---------|
| `task.assigned` | Orchestrator | Agent | `{"task_id", "description", "priority"}` |
| `task.completed` | Agent | Orchestrator | `{"task_id", "result", "artifacts"}` |
| `task.failed` | Agent | Orchestrator | `{"task_id", "error", "retry_count"}` |
| `code.generated` | Coder | Reviewer, Tester | `{"code", "language", "task_id"}` |
| `code.reviewed` | Reviewer | Coder | `{"issues", "approval", "suggestions"}` |
| `research.findings` | Researcher | Planner, Coder | `{"findings", "sources", "confidence"}` |
| `memory.stored` | Any | — | `{"memory_type", "content", "tags"}` |
| `ping` | Any | Any | `{"requester"}` — heartbeat check |

### 4.4 Shared Memory Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    Five-Layer Memory Architecture               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: WORKING MEMORY (in-process, per-agent)               │
│  ─────────────────────────────────────────────────────           │
│  - Fast, ephemeral, scoped to single task execution            │
│  - Stores: current context, scratchpad, active tool state     │
│  - Auto-cleared between tasks                                   │
│  - Implementation: dict per agent, thread-safe via asyncio      │
│                                                                 │
│  Layer 2: EPISODIC MEMORY (SQLite)                             │
│  ─────────────────────────────────────────────────────           │
│  - Records significant events and agent actions                 │
│  - Schema:                                                       │
│    episodes(id, agent_id, task_id, event_type, content,        │
│              timestamp, importance_score)                       │
│  - Retrieval: by agent, task, time range, importance           │
│  - Auto-archive after 30 days (configurable)                    │
│                                                                 │
│  Layer 3: SEMANTIC MEMORY (ChromaDB)                           │
│  ─────────────────────────────────────────────────────           │
│  - Vector embeddings of facts, knowledge, learned concepts     │
│  - Schema:                                                       │
│    embeddings(id, content, embedding_vector, metadata,         │
│                created_by_agent, created_at, tags)             │
│  - Retrieval: similarity search, filtered by agent/tag/time    │
│  - Embedding model: nomic-embed-text (installed locally)        │
│                                                                 │
│  Layer 4: LONG-TERM MEMORY (SQLite)                            │
│  ─────────────────────────────────────────────────────           │
│  - Persists across sessions, high-value knowledge               │
│  - Schema:                                                       │
│    knowledge(id, content, category, confidence, source_agent,  │
│              verified, verified_at, created_at, updated_at)    │
│  - Only written by Meta-Learner agent                           │
│  - Periodic deduplication against semantic memory               │
│                                                                 │
│  Layer 5: SKILL MEMORY (SQLite)                                │
│  ─────────────────────────────────────────────────────           │
│  - Stores learned tool-use patterns, prompt strategies          │
│  - Schema:                                                       │
│    skills(id, skill_name, description, prompt_template,        │
│            success_rate, use_count, last_used, created_at)      │
│  - Updated by Meta-Learner after each task completion          │
│  - Used by agents to select best strategies for task types      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Memory Access Patterns:**

```python
class MemoryManager:
    async def store_episode(agent_id: str, event: Episode) -> str: ...
    async def retrieve_episodes(
        agent_id: str | None = None,
        task_id: str | None = None,
        since: datetime | None = None,
        min_importance: int = 5
    ) -> list[Episode]: ...

    async def store_semantic(
        content: str,
        created_by_agent: str,
        tags: list[str],
        metadata: dict | None = None
    ) -> str: ...
    async def retrieve_semantic(
        query: str,
        top_k: int = 10,
        filter_tags: list[str] | None = None,
        filter_agents: list[str] | None = None
    ) -> list[SemanticMemory]: ...

    async def store_knowledge(
        content: str,
        category: str,
        confidence: float,
        source_agent: str
    ) -> str: ...
    async def retrieve_knowledge(
        category: str | None = None,
        min_confidence: float = 0.7
    ) -> list[Knowledge]: ...

    async def store_skill(
        skill_name: str,
        prompt_template: str,
        success_rate: float,
        use_count: int
    ) -> str: ...
    async def retrieve_skills(
        task_type: str | None = None,
        min_success_rate: float = 0.5
    ) -> list[Skill]: ...

    async def consolidate(agent_id: str) -> ConsolidationReport:
        """Move high-importance episodes → semantic memory,
           deduplicate semantic → long-term knowledge."""
```

### 4.5 SwarmOrchestrator

```python
@dataclass
class Task:
    id: str
    description: str
    task_type: TaskType             # CODE | RESEARCH | ANALYSIS | CREATIVE | GENERAL
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    assigned_agent: str | None = None
    deadline: datetime | None = None
    metadata: dict = field(default_factory=dict)

@dataclass
class TaskGraph:
    """Directed acyclic graph of tasks."""
    tasks: dict[str, Task]
    edges: list[tuple[str, str]]    # (prerequisite_task_id, dependent_task_id)

    def get_ready_tasks(self) -> list[Task]: ...
    def mark_complete(self, task_id: str) -> list[Task]: ...
    def is_complete(self) -> bool: ...

class SwarmOrchestrator:
    def __init__(
        self,
        agent_configs: list[AgentConfig],
        memory_manager: MemoryManager,
        message_bus: MessageBus,
        max_concurrent_agents: int = 5,
    ): ...

    async def receive_task(self, description: str) -> str:
        """Submit a task. Returns task_id. Non-blocking."""

    async def execute(self, task_id: str) -> TaskResult:
        """Execute a task through the full agent swarm. Blocking until done."""

    async def get_status(self, task_id: str) -> ExecutionStatus:
        """Get real-time status of task execution."""

    async def cancel(self, task_id: str) -> None:
        """Cancel a running task and all sub-tasks."""

    # Internal
    async def _plan(self, task: Task) -> TaskGraph: ...
    async def _dispatch(self, task: Task, agent: Agent) -> TaskResult: ...
    async def _monitor(self) -> None: ...
    async def _retry_failed(self, task_id: str, agent_id: str) -> None: ...
    async def _aggregate(self, task_id: str) -> TaskResult: ...
```

### 4.6 Agent Types

| Agent | Model | Strategy | Tools | Role |
|-------|-------|----------|-------|------|
| `orchestrator` | llama3.3:70b | PlanAndExecute | vector_search, memory | Master coordinator (separate from SwarmOrchestrator) |
| `planner` | llama3.3:70b | PlanAndExecute | vector_search, memory | Task decomposition, subtask assignment |
| `coder` | llama3.3:70b | ReAct | bash, read_file, write_file, python_repl, calculator | Code generation |
| `researcher` | llama3.3:70b | ReAct | web_search, url_fetch, vector_search | Information gathering |
| `reviewer` | llama3.3:70b | CoT | read_file, bash | Code review, quality assessment |
| `synthesizer` | llama3.3:70b | ToT | vector_search, memory | Consolidate findings from multiple agents |
| `meta_learner` | llama3.3:70b | PlanAndExecute | memory, vector_search | Pattern analysis, skill updates |

---

## 5. Database Schemas

### SQLite Tables

```sql
-- Episodes: agent actions and significant events
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,       -- 'action', 'tool_call', 'result', 'error'
    content TEXT NOT NULL,
    importance_score INTEGER DEFAULT 5,  -- 1-10
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_episodes_agent ON episodes(agent_id);
CREATE INDEX idx_episodes_task ON episodes(task_id);
CREATE INDEX idx_episodes_time ON episodes(created_at);

-- Knowledge: verified long-term facts
CREATE TABLE knowledge (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL,         -- 'fact', 'rule', 'pattern', 'strategy'
    confidence REAL NOT NULL,       -- 0.0-1.0
    source_agent TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_knowledge_category ON knowledge(category);
CREATE INDEX idx_knowledge_confidence ON knowledge(confidence);

-- Skills: learned tool-use patterns
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE,
    description TEXT,
    prompt_template TEXT NOT NULL,
    success_rate REAL DEFAULT 0.0,
    use_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_skills_name ON skills(skill_name);
CREATE INDEX idx_skills_success ON skills(success_rate DESC);

-- Tasks: execution tracking
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,           -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    assigned_agent TEXT,
    priority INTEGER DEFAULT 0,
    result TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX idx_tasks_status ON tasks(status);

-- Audit log: everything
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    task_id TEXT,
    action TEXT NOT NULL,
    details TEXT,                   -- JSON
    outcome TEXT,
    execution_time_ms REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audit_agent ON audit_log(agent_id);
CREATE INDEX idx_audit_task ON audit_log(task_id);
```

### ChromaDB Collection

```python
# Collection: semantic_memory
# Documents stored as:
# {
#     "id": str,
#     "embedding": np.array(768),    # nomic-embed-text
#     "document": str,                 # content
#     "metadata": {
#         "created_by_agent": str,
#         "tags": list[str],
#         "task_id": str,
#         "created_at": datetime,
#     }
# }
```

---

## 6. Configuration

### `config/agents.yaml`

```yaml
swarm:
  name: "yconic-agent-swarm"
  max_concurrent_agents: 5
  default_model: "ollama/llama3.3:70b"
  ollama_base_url: "http://localhost:11434"
  max_retries: 3
  task_timeout_seconds: 300
  memory:
    episodic_retention_days: 30
    semantic_top_k: 10
    knowledge_min_confidence: 0.7

agents:
  - name: planner
    role: planner
    model: "ollama/llama3.3:70b"
    strategy: PlanAndExecute
    tools: [vector_search, memory]
    max_retries: 2
    system_prompt: |
      You are the Planner agent. Your role is to decompose complex tasks
      into manageable subtasks and assign them to specialized agents.
      
      Guidelines:
      - Break down tasks into atomic, independent subtasks where possible
      - Identify dependencies between subtasks
      - Match subtask complexity to agent capabilities
      - Always include a verification/review step
      
  - name: coder
    role: coder
    model: "ollama/llama3.3:70b"
    strategy: ReAct
    tools: [bash, read_file, write_file, python_repl, calculator]
    max_retries: 3
    system_prompt: |
      You are the Coder agent. You write high-quality, well-tested code.
      
      Guidelines:
      - Write clean, readable, maintainable code
      - Always consider edge cases and error handling
      - Include docstrings and type hints
      - Run tests after writing code
      - Request review from the reviewer agent after completing code
      
  # ... (remaining agents follow same pattern)

tools:
  bash:
    enabled: true
    allowed_commands:
      - "python"
      - "pytest"
      - "git"
      - "ruff"
      - "ruff format"
    denied_patterns:
      - "rm -rf /"
      - "dd if="
      - ":(){ :|:& };:"
    timeout_seconds: 60

  python_repl:
    enabled: true
    timeout_seconds: 30
    max_output_lines: 100
    allowed_modules: ["math", "re", "json", "csv", "datetime", "collections"]
```

---

## 7. API Surface

### Python API

```python
from swarm import SwarmOrchestrator, AgentConfig

orchestrator = SwarmOrchestrator.from_config("config/agents.yaml")

# Non-blocking: submit and forget
task_id = await orchestrator.receive_task(
    "Build a REST API for a todo app with authentication"
)

# Blocking: wait for result
result = await orchestrator.execute(task_id)
print(result.final_answer)
print(result.artifacts)   # Files created, data gathered, etc.
print(result.execution_time_seconds)
print(result.agent_traces) # Full reasoning traces per agent
```

### CLI

```bash
# Run a task
python -m swarm.cli "Build a REST API for a todo app"

# Interactive mode
python -m swarm.cli --interactive

# List agents
python -m swarm.cli --agents

# Query memory
python -m swarm.cli --memory-search "authentication patterns"

# Run in daemon mode (background)
python -m swarm.cli --daemon --port 8080
```

### REST API (daemon mode)

```
POST   /tasks              Submit a new task
GET    /tasks/{id}         Get task status
GET    /tasks/{id}/result  Get full result
DELETE /tasks/{id}         Cancel task
GET    /agents             List active agents
POST   /agents/{name}/chat  Send message to agent
GET    /memory/search      Semantic search
GET    /health             Health check
```

---

## 8. Directory Structure

```
yconic_compute/
├── SPEC.md                          # This file
├── AGENTS.md                        # Agent manifest
├── config/
│   ├── agents.yaml                  # Agent and tool configuration
│   └── memory.yaml                  # Memory layer settings
├── src/
│   └── swarm/
│       ├── __init__.py
│       ├── main.py                  # CLI entry point
│       ├── orchestrator.py          # SwarmOrchestrator
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── agent.py             # Base Agent class
│       │   ├── strategies/
│       │   │   ├── __init__.py
│       │   │   ├── chain_of_thought.py
│       │   │   ├── tree_of_thought.py
│       │   │   ├── react.py
│       │   │   └── plan_and_execute.py
│       │   └── agents/
│       │       ├── __init__.py
│       │       ├── planner.py
│       │       ├── coder.py
│       │       ├── researcher.py
│       │       ├── reviewer.py
│       │       ├── synthesizer.py
│       │       └── meta_learner.py
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── manager.py          # MemoryManager (5-layer stack)
│       │   ├── episodic.py          # SQLite episodic memory
│       │   ├── semantic.py          # ChromaDB semantic memory
│       │   ├── long_term.py        # SQLite long-term knowledge
│       │   ├── skill.py            # SQLite skill memory
│       │   └── working.py          # In-memory working memory
│       ├── bus/
│       │   ├── __init__.py
│       │   └── message_bus.py      # A2A pub/sub bus
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py             # Tool protocol
│       │   ├── web_search.py
│       │   ├── url_fetch.py
│       │   ├── bash.py
│       │   ├── file_system.py
│       │   ├── python_repl.py
│       │   ├── calculator.py
│       │   └── vector_search.py
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── ollama_client.py    # Ollama API client
│       │   └── streaming.py        # Streaming response support
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.sql
│       │   ├── migrations/
│       │   │   └── 001_initial.sql
│       │   └── connection.py       # SQLite connection pool
│       ├── api/
│       │   ├── __init__.py
│       │   └── rest.py             # FastAPI REST server
│       └── types/
│           ├── __init__.py
│           ├── task.py
│           ├── message.py
│           └── result.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_memory.py
│   ├── test_message_bus.py
│   ├── test_orchestrator.py
│   ├── test_strategies.py
│   └── test_tools/
│       ├── test_bash.py
│       ├── test_python_repl.py
│       └── test_calculator.py
├── scripts/
│   ├── init_db.py                  # Initialize SQLite schema
│   ├── seed_memory.py              # Seed with initial knowledge
│   └── benchmark.py                # Performance benchmarks
├── .env.example
├── requirements.txt
└── README.md
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Foundation Classes)
- Project scaffolding, dependency installation
- SQLite schema initialization
- ChromaDB setup
- `OllamaClient` — async LLM calls with streaming
- `MessageBus` — A2A pub/sub core
- `MemoryManager` skeleton (all 5 layers)

### Phase 2: Agent Core
- `Agent` base class with state machine
- `ReasoningStrategy` implementations (CoT, ToT, ReAct, PlanAndExecute)
- `Tool` protocol and first 3 tools (bash, calculator, vector_search)
- Agent config loading from YAML

### Phase 3: Tool Server
- Remaining tools: web_search, url_fetch, read_file, write_file, python_repl
- Tool execution sandboxing (bash restrictions, python REPL limits)
- Tool registry and access control per agent

### Phase 4: Memory Integration
- Full `MemoryManager` implementation for all 5 layers
- Memory consolidation logic (episodes → semantic → long-term)
- Skill retrieval for agent strategy selection

### Phase 5: Orchestration
- `SwarmOrchestrator` — task receipt, decomposition, dispatch
- Task graph execution with dependency resolution
- Retry logic and failure recovery
- Result aggregation

### Phase 6: Specialized Agents
- Implement all 7 agent types (planner, coder, researcher, reviewer, synthesizer, meta_learner, orchestrator)
- Agent-specific system prompts
- A2A topic subscriptions per agent

### Phase 7: Observability
- Structured logging (JSON logs with agent_id, task_id, trace_id)
- Full audit trail in SQLite
- `ExecutionStatus` real-time tracking

### Phase 8: API & CLI
- FastAPI REST server (daemon mode)
- CLI with subcommands
- WebSocket support for streaming results

### Phase 9: Testing & Polish
- Unit tests for all components
- Integration tests for agent collaboration
- Benchmark suite

---

## 10. Acceptance Criteria

### Functional
- [ ] 5+ agents can run concurrently without crashing
- [ ] Agents communicate via A2A message bus (verified by trace logs)
- [ ] Task submitted via API/CLI completes with result
- [ ] All 5 memory layers store and retrieve correctly
- [ ] Reasoning strategies produce different outputs for same input
- [ ] Failed agents retry up to max_retries, then propagate failure
- [ ] Audit log contains every agent action with timestamps

### Performance
- [ ] Agent startup < 2 seconds (model pre-loaded by Ollama)
- [ ] Message bus latency < 10ms for in-process delivery
- [ ] Semantic search < 500ms for 10K embeddings
- [ ] System handles 5 concurrent agents on DGX Spark

### Quality
- [ ] Zero hardcoded values — all config from YAML
- [ ] Every async function has proper error handling
- [ ] Type hints on all public interfaces
- [ ] No tool can execute commands outside allowed patterns
- [ ] Memory consolidation runs without blocking agent execution

---

## 11. Key Design Decisions & Rationale

| Decision | Choice | Why |
|----------|--------|-----|
| **No LangChain/LlamaIndex** | Custom classes | Full control, no abstraction overhead, easier debugging |
| **SQLite for persistence** | SQLite + ChromaDB | Battle-tested, zero-config, perfect for single-node |
| **In-process message bus** | asyncio pub/sub | No network overhead, simple, sufficient for local |
| **YAML configuration** | YAML | Declarative, human-editable, version-controllable |
| **5 reasoning strategies** | CoT/ToT/ReAct/PaE | Covers the main reasoning paradigms from curriculum |
| **5 memory layers** | Working/Episodic/Semantic/LongTerm/Skill | Matches curriculum Module 3 exactly |
| **One Ollama model** | llama3.3:70b | Consistent behavior across agents, DGX Spark handles it |
| **Async throughout** | asyncio | Non-blocking I/O for concurrent agents, proper concurrency |
| **Task graph DAG** | Directed acyclic graph | Ensures no circular dependencies, clear execution order |
