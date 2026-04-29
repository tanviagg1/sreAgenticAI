# AI Learnings — SRE Agentic AI

> A living reference document. Updated as each phase is built.
> Read this alongside the code — every concept here maps to something in the codebase.

---

## Table of Contents

1. [Foundational Concepts](#1-foundational-concepts)
2. [Prompt Engineering](#2-prompt-engineering)
3. [Tool Use & Function Calling](#3-tool-use--function-calling)
4. [The ReAct Pattern](#4-the-react-pattern)
5. [Retrieval Augmented Generation (RAG)](#5-retrieval-augmented-generation-rag)
6. [Vector Embeddings & Semantic Search](#6-vector-embeddings--semantic-search)
7. [Agent Memory](#7-agent-memory)
8. [Multi-Agent Orchestration](#8-multi-agent-orchestration)
9. [LangGraph — Stateful Agent Graphs](#9-langgraph--stateful-agent-graphs)
10. [Self-Reflection & Critique](#10-self-reflection--critique)
11. [Human-in-the-Loop](#11-human-in-the-loop)
12. [Testing AI Systems](#12-testing-ai-systems)
13. [Glossary](#13-glossary)
14. [Phase-by-Phase Summary](#14-phase-by-phase-summary)

---

## 1. Foundational Concepts

### What is an LLM?
A Large Language Model is a neural network trained on massive text data. It predicts the next token
(word/subword) given a sequence. By predicting text well enough, it learns reasoning, coding,
summarization, and more.

- **Llama 3.1** (used here): Open-source LLM by Meta. Runs locally via Ollama. 8B parameters = 8 billion weights.
- **Ollama**: A tool that serves LLMs locally as a REST API. Think of it as Docker for LLMs.

### What is an Agent?
An agent is an LLM given:
1. A goal (via a prompt)
2. Tools it can call (functions, APIs)
3. A loop — it reasons, acts, observes, repeats until done

An agent is NOT just an LLM call. It is LLM + tools + loop + memory.

### What is a Multi-Agent System?
Multiple specialized agents working together. Each agent is good at one thing.
An orchestrator coordinates them — decides who does what and when.
Agents can run sequentially, in parallel, or conditionally.

---

## 2. Prompt Engineering

Prompt engineering is the practice of crafting inputs to LLMs to get reliable, high-quality outputs.

### System Prompt vs Human Prompt
```
System:  "You are an SRE expert. Be concise. Use bullet points."
Human:   "What does this error mean: OOMKilled"
```
- System prompt: Sets persona, rules, output format. Applied to every message.
- Human prompt: The actual task/question.

### Zero-Shot Prompting
No examples given. Just ask.
```
"Analyze this log and identify the root cause."
```

### Few-Shot Prompting
Give 2-3 examples before the real task. Dramatically improves consistency.
```
"Example 1: Log: ... -> Root cause: memory leak
 Example 2: Log: ... -> Root cause: network timeout
 Now analyze: ..."
```

### Chain-of-Thought (CoT)
Ask the model to think step by step before answering.
```
"Think step by step. First identify the error type, then the affected service, then the likely cause."
```
Why it works: forces the model to show its work — intermediate reasoning improves the final answer.

### Structured Output Prompting
Force the LLM to respond in JSON or a specific schema.
```
"Respond ONLY in JSON with keys: {severity, service, root_cause, recommended_action}"
```

### Prompt Templates
Parameterized prompts — like string templates with variables filled at runtime.
```python
template = "Analyze the following {log_type} log:\n{log_content}\nReturn severity and root cause."
```
In code: prompts/health_prompts.py, prompts/retrieval_prompts.py

---

## 3. Tool Use & Function Calling

LLMs can be given tools — Python functions the model can choose to call.

### How it works
1. You describe the tool to the LLM (name, description, parameters via docstring)
2. The LLM decides IF and WHEN to call it
3. The tool runs, returns a result
4. The LLM uses that result to continue reasoning

### Example
```python
@tool
def check_container_health(container_name: str) -> dict:
    """Check if a container is running and healthy."""
    return mock_containers.get(container_name, {"status": "unknown"})
```
The LLM reads the docstring and knows when to call this function.

### Why this is powerful
The LLM does not just generate text — it can act on the world:
query databases, read files, call APIs, check container status.

In this project: skills/container_health.py

---

## 4. The ReAct Pattern

ReAct = Reason + Act. The most important agent pattern.

### The Loop
```
Thought:     "I need to check if nginx is running"
Action:      check_container_health("nginx")
Observation: {"status": "unhealthy", "reason": "OOMKilled"}
Thought:     "nginx is OOMKilled. I should check memory usage."
Action:      get_unhealthy_containers()
Observation: [nginx, worker, app-server]
Thought:     "I have enough info. Three containers need attention."
Final Answer: "nginx is OOMKilled. worker is stopped. app-server is degraded."
```

### Why it works
- Breaks the task into small, verifiable steps
- Each action gives new information that guides next reasoning
- Much more reliable than one-shot answering

In LangChain: create_react_agent. The agent loop runs until it produces a Final Answer.

---

## 5. Retrieval Augmented Generation (RAG)

RAG = giving the LLM relevant documents before it answers.

### The Problem RAG Solves
LLMs have a training cutoff. They do not know:
- Your company's runbooks
- Your specific service architecture
- Logs from last night
- Last week's incident report

### How RAG Works
```
User query -> Embed query -> Search vector DB -> Retrieve top-k docs
                                                        |
                                        LLM prompt = query + retrieved docs
                                                        |
                                               Grounded answer
```

### RAG Components
| Component        | Tool Used          | What it does                          |
|------------------|--------------------|---------------------------------------|
| Document loader  | LangChain          | Reads files, PDFs, web pages          |
| Text splitter    | LangChain          | Chunks documents into pieces          |
| Embeddings model | nomic-embed-text   | Converts text to vectors              |
| Vector store     | ChromaDB           | Stores and searches vectors           |
| Retriever        | LangChain          | Finds top-k relevant chunks           |
| LLM              | Llama 3.1          | Generates answer from chunks          |

### Chunking Strategies
- Fixed size: Split every 500 chars. Simple but may cut mid-sentence.
- Recursive: Split on paragraphs then sentences then words. Better.
- Semantic: Split by meaning. Best but slower.

In this project: skills/vector_store.py, mocks/runbooks/

---

## 6. Vector Embeddings & Semantic Search

### What is an Embedding?
An embedding converts text into a list of numbers (a vector) that captures meaning.

```
"nginx container is down"    -> [0.23, -0.81, 0.44, ...]  (384 dimensions)
"nginx service not running"  -> [0.21, -0.79, 0.46, ...]  (very similar)
"postgres database crashed"  -> [-0.12, 0.33, -0.67, ...]  (different meaning)
```

Similar meanings produce similar vectors — close together in vector space.

### Similarity Search
When you query ChromaDB:
1. Your query is embedded
2. ChromaDB finds stored vectors closest to your query vector
3. Returns the matching documents

This is semantic search — finds meaning, not just keywords.
"OOMKilled" and "out of memory" mean the same thing — semantic search finds both.

---

## 7. Agent Memory

### Types of Memory

| Type           | What it is                                   | Lasts            |
|----------------|----------------------------------------------|------------------|
| In-context     | The conversation so far                      | This session     |
| Summary memory | LLM summarizes old context to save tokens    | This session     |
| Entity memory  | Tracks named entities (services, errors)     | Configurable     |
| Vector memory  | Past interactions stored as embeddings       | Persistent       |
| External store | Redis, database                              | Persistent       |

In this project:
- Short-term: LangChain ConversationBufferMemory
- Long-term: ChromaDB (past incidents)
- Working memory: LangGraph state

---

## 8. Multi-Agent Orchestration

### Supervisor Pattern (used in Phase 5)
One orchestrator agent reads the task and routes to specialists.
```
User input
    |
Orchestrator -> Retrieval Agent -> log analysis
             -> Citation Agent  -> runbook lookup
             -> Coding Agent    -> generate fix
             -> Health Agent    -> verify fix worked
```

### Parallel Pattern
Multiple agents run simultaneously on independent subtasks.
Results are merged by the orchestrator.

### Sequential Pipeline
Output of one agent is input to the next. Like Unix pipes.

### Agent Communication
Agents share state through a shared state object (LangGraph TypedDict).
Each agent reads what it needs and writes its output back to shared state.

---

## 9. LangGraph — Stateful Agent Graphs

LangGraph models agent workflows as a directed graph.

### Key Concepts
- Node: A function (or agent) that does some work
- Edge: Connection between nodes — defines flow
- Conditional edge: "If X go to node A, else go to node B"
- State: Shared dictionary passed between all nodes

### Example Graph
```python
graph = StateGraph(SREState)
graph.add_node("health_check", health_agent)
graph.add_node("log_retrieval", retrieval_agent)
graph.add_node("code_fix", coding_agent)

graph.add_edge("health_check", "log_retrieval")
graph.add_conditional_edges(
    "log_retrieval",
    should_fix_code,
    {"yes": "code_fix", "no": END}
)
```

### Why LangGraph over simple chains?
- Cycles: Agents can loop back (retry, re-check)
- Branching: Different paths based on what was found
- Visibility: Graph is inspectable and visualizable
- State persistence: Pause and resume mid-graph

---

## 10. Self-Reflection & Critique

An agent that checks its own output before returning it.

```
Coding Agent generates a fix
        |
Reflection step: "Is this fix safe? Does it handle edge cases?"
        |
If not good enough: regenerate
        |
If good: return to orchestrator
```

Why it matters: LLMs can hallucinate. Self-critique catches errors before they reach production.
Creates a draft -> review -> revise loop like a human engineer would do.

Implementation: a second LLM call with a critique prompt:
```
"Here is a code fix. Critique it. Does it solve the problem without introducing new bugs?
Rate confidence 1-10. If below 7, explain what is wrong."
```

---

## 11. Human-in-the-Loop

### The Pattern
Add approval gates before destructive actions:
```
Coding Agent: "I want to increase memory limit from 512MB to 1GB"
                    |
            [PAUSE — await human approval]
                    |
        Human: "approved" or "rejected"
                    |
            Continue or abort
```

### Levels of Autonomy
| Level | Agent can...                                        |
|-------|-----------------------------------------------------|
| 0     | Only suggest — human does everything                |
| 1     | Read-only actions (check logs, check health)        |
| 2     | Write actions with approval gate                    |
| 3     | Fully autonomous with audit log                     |

This project implements Levels 1-2.

---

## 12. Testing AI Systems

Testing AI is different from testing regular software. Outputs are probabilistic.

### Unit Tests — deterministic parts only, no LLM
Test tools and skills in isolation:
```python
def test_container_health_returns_status():
    result = check_container_health.invoke({"container_name": "nginx"})
    assert "status" in result
    assert result["status"] == "unhealthy"
```

### Integration Tests — agent + tools with real LLM
```python
def test_health_agent_detects_down_container():
    result = run_health_check()
    assert "nginx" in result["output"].lower()
```

### End-to-End Tests — full pipeline from trigger to output
```python
def test_full_sre_pipeline():
    result = run_full_pipeline(scenario="nginx_oom")
    assert result["fix_suggested"] is True
    assert result["severity"] == "high"
```

### LLM Evaluation (AI-specific)
- Faithfulness: Is the answer grounded in retrieved docs?
- Relevance: Does it answer the actual question?
- Hallucination detection: Did it make something up?

Tools: pytest for all tests, deepeval for LLM eval (Phase 5).

---

## 13. Glossary

| Term              | Meaning                                                                              |
|-------------------|--------------------------------------------------------------------------------------|
| Token             | A word or subword. ~750 words = ~1000 tokens                                         |
| Context window    | Max tokens an LLM can process at once. Llama 3.1 8B: 128k tokens                   |
| Temperature       | Randomness of output. 0 = deterministic. 1 = creative. Use 0 for SRE tasks          |
| Embedding         | A vector (list of numbers) representing text meaning                                 |
| Vector DB         | Database that stores and searches embeddings (ChromaDB, Pinecone, Weaviate)          |
| RAG               | Retrieval Augmented Generation — grounding LLM answers in real documents             |
| Agent             | LLM + tools + loop                                                                   |
| Tool / Skill      | A Python function an agent can call                                                  |
| ReAct             | Reason + Act loop — the core agent pattern                                           |
| LangChain         | Python framework for building LLM apps                                               |
| LangGraph         | Extension of LangChain for stateful graph-based agents                               |
| Ollama            | Local LLM server — runs Llama, Mistral, etc. on your machine                        |
| Llama 3.1         | Meta's open-source LLM. 8B = small/fast, 70B = larger/smarter                      |
| nomic-embed-text  | Open-source embedding model, runs via Ollama                                         |
| ChromaDB          | Open-source local vector database                                                    |
| Chunking          | Splitting documents into smaller pieces for retrieval                                |
| Hallucination     | LLM confidently states something false                                               |
| Grounding         | Connecting LLM output to real data to reduce hallucinations                          |
| Supervisor        | Orchestrator agent that routes tasks to specialist agents                            |
| State             | Shared data object passed between LangGraph nodes                                    |
| Human-in-the-loop | Requiring human approval before an agent takes action                               |
| Self-reflection   | Agent critiquing its own output before returning it                                  |
| Semantic search   | Search by meaning (via embeddings), not keywords                                     |
| Inference         | Running an LLM to generate output (vs training)                                     |
| OOMKilled         | Out Of Memory Killed — Linux kernel killed a process that used too much RAM          |
| CoT               | Chain-of-Thought — prompting technique that asks the model to reason step by step    |
| Few-shot          | Providing examples in the prompt to guide LLM output format and quality              |
| Zero-shot         | No examples given — LLM answers from training knowledge alone                       |

---

## 14. Phase-by-Phase Summary

| Phase | Branch                       | Agents Built      | Concepts Introduced                                              |
|-------|------------------------------|-------------------|------------------------------------------------------------------|
| 1     | phase/1-health-agent         | Health Agent      | Prompt engineering, tool use, ReAct, Ollama setup               |
| 2     | phase/2-retrieval-log-agent  | Retrieval Agent   | RAG, vector embeddings, ChromaDB, chunking strategies           |
| 3     | phase/3-citation-rag-agent   | Citation Agent    | Agent memory, grounding, citation patterns                       |
| 4     | phase/4-coding-agent         | Coding Agent      | Code generation, structured output, self-reflection              |
| 5     | phase/5-orchestration        | Orchestrator      | LangGraph, multi-agent patterns, human-in-the-loop, LLM eval    |

---

*Updated as each phase is completed. Check git history for changes to this file.*
