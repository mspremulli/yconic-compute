# Multi-Agent AI Hackathon Projects for NVIDIA DGX Spark

> Weekend builds that fuse the [Autonomous Multi-Agent AI Systems](https://yconic.ai/claudearnell/multiai) curriculum with the raw horsepower of the **NVIDIA DGX Spark** — 128 GB unified CPU+GPU memory, GB10 Blackwell GPU, and CUDA 13.0.

---

## 1. GAIA Benchmark Swarm — Divide-and-Conquer Agent Evaluation

Deploy 5+ agent instances simultaneously, each running a different reasoning strategy (Chain-of-Thought, Tree-of-Thought, ReAct, Plan-and-Execute) from Module 2 against the GAIA benchmark. A coordinator agent collects results, runs head-to-head comparisons, and builds a live leaderboard — all on-device.

**What you build:**
- Parallel agent runner that launches one 7B–13B model instance per reasoning strategy
- Shared SQLite evaluation harness (Module 1) logging all runs with the 12-category failure taxonomy
- Coordinator agent that performs real-time ablation analysis across strategies and difficulty levels

**Why DGX Spark:** Running 5+ concurrent LLM instances each with full tool-use pipelines (web search, URL fetch, calculator) requires ~60–80 GB of memory. Consumer GPUs top out at one, maybe two instances.

---

## 2. Five-Layer Memory Stack on a Local 30B+ Model

Implement the complete Five-Layer Agent Memory Stack (Module 3) — working, episodic, semantic, long-term, and skill memory — backed by a 30B+ parameter model with 100K+ token context windows, entirely on-device with no cloud calls.

**What you build:**
- Vector store for semantic memory with local embeddings (no API dependency)
- SQLite-backed episodic and long-term memory with retrieval and decay
- Skill memory that persists learned tool-use patterns across sessions
- Working memory manager that dynamically promotes/demotes across layers based on relevance

**Why DGX Spark:** The memory stack needs a large model for nuanced recall and reasoning, plus a concurrent embedding model for semantic indexing. A 30B model at full precision + embeddings + vector DB = 80–100 GB. Laptops need extreme quantization that degrades memory retrieval quality.

---

## 3. Seven-Agent Claims Processing Pipeline

Replicate the Module 5 multi-agent orchestration pattern: build a seven-agent pipeline where each agent specializes in a different stage of claims processing (intake, validation, policy lookup, damage assessment, fraud detection, adjudication, communication) — all running as separate model instances on one machine.

**What you build:**
- Seven specialized agents, each a fine-tuned or prompted 7B–13B model instance
- A2A communication bus (Module 4) for structured inter-agent messaging
- AGENTS.md manifests describing each agent's capabilities and contracts
- Orchestrator that manages workflow dependencies and handles agent failures gracefully

**Why DGX Spark:** Seven concurrent model instances + the orchestrator + shared state = ~90–110 GB memory footprint. This pipeline is impossible on consumer hardware without serializing agents (destroying the real-time processing advantage).

---

## 4. Self-Improving Code Agent Team

Build the Module 6 autonomous coding agent team with a twist: wire in the Module 9 self-improvement loop so agents learn from their own execution traces. One agent writes code, another reviews it, a third runs tests, and a fourth analyzes failure patterns to update the team's shared skill memory.

**What you build:**
- Four-agent team: Coder (30B+ code LLM), Reviewer, Tester, and Meta-Learner
- MCP server (Module 4) exposing local filesystem, git, and test runner as tools
- Feedback loop where the Meta-Learner agent updates a shared skill memory store after each code-review-test cycle
- Evaluation harness tracking pass rates, review acceptance rates, and improvement curves over iterations

**Why DGX Spark:** The Coder agent alone needs a large code model (30B+) with long context for full-repo reasoning. Add three more concurrent agent instances plus the MCP tool server, and you're well past 100 GB. Quantizing the code model to fit on a laptop measurably degrades code generation quality.

---

## 5. Multi-Strategy Reasoning Tournament with Live Visualization

Run a live tournament where agents using different reasoning architectures (Module 2) compete on progressively harder tasks. Visualize reasoning traces, tool calls, token usage, and failure modes in a real-time dashboard — a spectator sport for AI reasoning.

**What you build:**
- Four concurrent agent instances, each locked to one strategy (CoT, ToT, ReAct, Plan-and-Execute)
- RLVR scoring pipeline that verifies answers in domains with checkable correctness (math, code, factual lookup)
- Streaming dashboard showing live reasoning traces, tool invocations, and head-to-head scores
- Post-tournament analysis: failure taxonomy breakdown per strategy, token efficiency comparisons

**Why DGX Spark:** Four simultaneous 13B model instances running multi-step tool-use chains generate heavy, sustained GPU load. The dashboard adds a rendering burden on top. Needs ~50–70 GB memory and consistent throughput that consumer GPUs can't sustain without thermal throttling.

---

## 6. Privacy-First Medical Claims Agent Swarm

Combine Module 5 orchestration with Module 7 safety and governance to build a HIPAA-compliant multi-agent system that processes medical claims entirely on-device. Every agent has guardrails enforcing data residency, PII redaction, and audit logging — demonstrating that autonomous agents can be trustworthy with sensitive data.

**What you build:**
- Five-agent pipeline: Intake, Medical Coding (ICD-10 lookup), Policy Matching, Audit, and Decision agents
- Safety layer (Module 7) wrapping every agent with PII detection, output filtering, and constraint enforcement
- Complete audit trail in local SQLite — every agent action, tool call, and decision logged with timestamps
- Governance dashboard showing constraint violations, overrides, and compliance metrics

**Why DGX Spark:** Medical coding requires a knowledgeable model (30B+) plus four supporting agents, safety wrappers running inference on every message, and a local vector store of medical codes. Total memory: ~80–110 GB. The zero-cloud-dependency requirement makes DGX Spark the natural fit — data never leaves the box.

---

## 7. Distributed Agent Mesh Across Two DGX Sparks

If you have access to two DGX Sparks, implement Module 11's distributed agent systems: split a 10-agent swarm across both machines with real-time A2A communication over the network. Demonstrate fault tolerance by killing agents on one node and watching the mesh recover.

**What you build:**
- A2A network layer (Module 4) extended with gRPC or ZeroMQ for cross-machine communication
- Agent placement scheduler that distributes agents based on memory and compute availability
- Fault tolerance: heartbeat monitoring, agent migration, and task reassignment on node failure
- Benchmark comparing single-node vs. distributed performance on GAIA Level 2 and 3 tasks

**Why DGX Spark:** Each node runs 5+ agents at full fidelity. A distributed agent mesh needs both nodes to carry real concurrent load — not just route messages. Two DGX Sparks give you 256 GB of total agent-addressable memory with Blackwell-class throughput on both ends.

---

## 8. Agent Capability Compounding Lab

Build the Module 9 self-improving agent as a weekend experiment: start with a base agent that scores ~40% on GAIA Level 1, then let it run iterative self-improvement cycles — analyzing its own failure traces, updating its skill memory, and re-running the benchmark — tracking how the score curve evolves over 50+ improvement cycles.

**What you build:**
- Base agent with Module 1 evaluation harness and Module 3 memory stack
- Self-improvement loop: run GAIA batch → categorize failures (12-type taxonomy) → generate hypotheses → update prompts/tool strategies → re-run
- Persistent skill memory that accumulates learned patterns across cycles
- Improvement curve visualization: accuracy, failure distribution shifts, and token efficiency over time

**Why DGX Spark:** Each improvement cycle runs the full GAIA evaluation suite (hundreds of multi-step tasks with tool use). Running 50+ cycles in a weekend requires sustained GPU throughput. A consumer GPU would need days; the DGX Spark can iterate in hours, making the experiment feasible within a hackathon.

---

## Quick Reference

| # | Project | Agents | Est. Memory | Key Modules |
|---|---------|--------|-------------|-------------|
| 1 | GAIA Benchmark Swarm | 5–6 | ~70 GB | 1, 2 |
| 2 | Five-Layer Memory Stack | 1–2 | ~90 GB | 3 |
| 3 | Claims Processing Pipeline | 7 | ~100 GB | 4, 5 |
| 4 | Self-Improving Code Team | 4 | ~110 GB | 4, 6, 9 |
| 5 | Reasoning Tournament | 4 | ~60 GB | 1, 2 |
| 6 | Medical Claims + Safety | 5 | ~100 GB | 5, 7 |
| 7 | Distributed Agent Mesh | 10 | ~256 GB (2 nodes) | 4, 11 |
| 8 | Capability Compounding Lab | 1 | ~50 GB | 1, 3, 9 |

---

## Getting Started

1. **Pick your model backbone.** Most projects work well with Llama 3 8B/70B or Mixtral. Use the 70B variant for single-agent projects (2, 8) and 7B–13B for multi-agent swarms (1, 3, 5, 6, 7).
2. **Start with Module 1's evaluation harness.** Every project benefits from structured logging and failure categorization — wire it in first.
3. **Use AGENTS.md from Module 4.** Even for solo-agent projects, writing an AGENTS.md manifest forces you to define capabilities and constraints upfront.
4. **Benchmark early.** Run your baseline within the first two hours. The rest of the weekend is for iteration.

---

*Built on the [Autonomous Multi-Agent AI Systems](https://yconic.ai/claudearnell/multiai) curriculum. Designed for the NVIDIA DGX Spark.*
