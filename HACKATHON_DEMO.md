# Autonomous Agent Swarm - Hackathon Demo

## Part 1: OpenCode Introduction

### What is OpenCode?
- OpenCode is an interactive CLI tool for software engineering tasks
- It works as an autonomous AI coding assistant in your terminal
- Unlike chat-based AI, it can actually execute code, run commands, and make changes

### Key Features
- **Interactive CLI** - Works in your terminal, not a web browser
- **Execute code** - Can run Python, bash, and other commands
- **File operations** - Read, write, and edit files
- **Web search** - Can search the web for information
- **Multi-step tasks** - Can handle complex, multi-file projects

### Demo Commands
```
# Ask simple questions
opencode "What is 2+2?"

# Ask it to do tasks
opencode "Create a Python script that fetches stock prices"

# It can:
# - Search the web for docs
# - Read existing code
# - write_file new files
# - Run tests
# - Execute shell commands
```

### Why It Matters for Autonomous Companies
- Reduces manual coding effort by 50%+
- Acts as a tireless developer that works 24/7
- Can delegate repetitive tasks
- Accelerates prototyping

---

## Part 2: Building the Swarm Agent

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SwarmOrchestrator                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Planner │─▶│ Coder   │─▶│ Reviewer│─▶│Synthesis│       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│       │            │            │            │              │
│       └────────────┴────────────┴────────────┘              │
│                         │                                  │
│              ┌──────────┴──────────┐                       │
│              │    MessageBus       │                       │
│              │  (Pub/Sub)         │                       │
│              └────────────────────┘                       │
│                         │                                  │
│    ┌────────────────────┼────────────────────┐            │
│    │                    │                    │            │
│ ┌──┴───┐          ┌────┴───┐          ┌────┴───┐         │
│ │Memory│          │Memory │          │Memory  │         │
│ │Episo-│          │Seman- │          │Working │         │
│ │dic   │          │tic    │          │        │         │
│ └──────┘          └───────┘          └────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Agents
- **Planner** - Breaks tasks into subtasks
- **Coder** - Writes code
- **Researcher** - Gathers information
- **Reviewer** - Reviews code for bugs/issues
- **Synthesizer** - Combines results
- **Meta-Learner** - Learns from past tasks

#### 2. Tools
- **Bash** - Execute shell commands
- **read_file/write_file** - File operations
- **PythonRepl** - Run Python code
- **WebSearch** - Search the web
- **MemoryTools** - Store/retrieve knowledge

#### 3. Memory System
- **Episodic** - Stores task execution history
- **Semantic** - Stores knowledge/patterns
- **Working** - Short-term context

#### 4. Message Bus
- Pub/Sub pattern for agent communication
- Topics: `task.assigned`, `task.completed`, `task.failed`

### How It Works

1. **Task Submission** → Planner decomposes into subtasks
2. **Task Distribution** → Subtasks assigned to appropriate agents
3. **Parallel Execution** → Multiple agents work simultaneously
4. **Result Aggregation** → Synthesizer combines outputs
5. **Learning** → Meta-Learner updates memory for future tasks

### Live Demo Script

```bash
# Start the frontend
streamlit run app.py

# Submit a task:
# "What is the capital of France?"
# "Write a hello world function in Python"
# "Analyze the code in src/swarm"
```

### Why Autonomous Companies Need This

1. **Scale** - Handle unlimited parallel tasks
2. **Specialization** - Each agent excels at one thing
3. **Memory** - Learns from past work
4. **Cost** - Runs on your own hardware (Ollama)
5. **Privacy** - No data leaves your server

### Technical Stack
- **LLM**: Ollama (local Llama3)
- **Backend**: Python + FastAPI
- **Frontend**: Streamlit
- **Database**: SQLite + ChromaDB
- **Messaging**: In-memory pub/sub

### Future Enhancements
- Add more specialized agents (security, testing, docs)
- Integrate with GitHub/GitLab for autonomous PRs
- Add persistent message queue (Redis)
- Implement agent-to-agent negotiation
- Add monitoring/dashboards
