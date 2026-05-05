# SRE Agentic AI — Project Learnings Summary

## What Was Built

A fully local, open-source multi-agent SRE system built across 5 phases:

| Phase | Agent | What it does |
|---|---|---|
| 1 | Health Agent | Checks container health using ReAct loop + tool calling |
| 2 | Retrieval Agent | Semantically searches logs via RAG and ChromaDB |
| 3 | Citation Agent | Looks up SRE runbooks and past incidents, cites sources |
| 4 | Coding Agent | Generates config fixes, critiques them, gates on human approval |
| 5 | Orchestrator | Wires all agents with LangGraph StateGraph + conditional routing |

**Stack:** Ollama + Llama 3.1, LangChain 1.x, LangGraph, ChromaDB, nomic-embed-text, FastAPI, pytest

**Everything runs locally** — no API keys, no cloud, no external services.

---

## AI Concepts Learned

### Foundations
- **LLM inference** — running a large language model locally via Ollama
- **Temperature** — 0 for deterministic SRE tasks, higher for creative tasks
- **Context window** — how much an LLM can "see" at once
- **Tokens** — how LLMs process text

### Prompt Engineering
- **System prompts** — setting agent persona and rules
- **Zero-shot prompting** — asking without examples
- **Few-shot prompting** — providing examples to guide output format
- **Chain-of-thought (CoT)** — asking the model to reason step by step
- **Structured output prompting** — forcing JSON schema compliance
- **Anti-hallucination prompting** — rules like "only use what you find in the logs"

### Tool Use & Agents
- **Tool use / function calling** — giving an LLM Python functions to call
- **@tool decorator** — how docstrings become tool descriptions
- **ReAct pattern** — Thought → Action → Observation loop
- **AgentExecutor / create_agent** — wiring LLM + tools into a loop
- **Principle of least privilege** — only give agents the tools they need

### RAG (Retrieval Augmented Generation)
- **RAG pipeline** — load → chunk → embed → store → retrieve → generate
- **Vector embeddings** — converting text to semantic number vectors
- **Semantic search** — finding meaning, not just keywords
- **ChromaDB** — local vector database with persistent collections
- **Chunking strategies** — RecursiveCharacterTextSplitter vs MarkdownHeaderTextSplitter
- **Chunk size and overlap** — trade-offs between precision and context
- **Document metadata** — storing source info alongside chunks for citation
- **Multi-collection RAG** — separate vector stores for logs vs runbooks
- **Grounding** — anchoring LLM answers in retrieved data
- **Source attribution / citation** — citing which document a recommendation came from

### Agent Memory
- **Short-term memory** — conversation history in LangGraph messages list
- **Long-term memory** — past incidents stored in ChromaDB across sessions
- **Seeding memory** — pre-populating a vector store with historical data
- **Multi-turn conversation** — passing conversation history between calls

### Code Generation
- **Structured output** — LLM responds in a strict JSON schema
- **Grounded code generation** — reading real config before generating a fix
- **Self-reflection** — second LLM call critiques the first LLM's output
- **Generate → critique → revise loop** — iterative improvement with confidence scores
- **Human-in-the-loop** — approval gate before any destructive action

### Multi-Agent Orchestration (LangGraph)
- **StateGraph** — directed graph where agents are nodes
- **Shared state (TypedDict)** — all agents read/write one typed dict
- **Nodes** — functions that take state and return state updates
- **Fixed edges** — always go from A to B
- **Conditional edges** — route based on what was found (CRITICAL vs HEALTHY)
- **Supervisor pattern** — orchestrator decides which specialist to call
- **MemorySaver checkpointer** — saves state at every step, enables resumable runs
- **thread_id** — identifies individual pipeline runs in the checkpointer

### Testing AI Systems
- **Unit tests** — test tools and deterministic logic without LLM
- **Integration tests** — test agent + tools with real LLM
- **End-to-end tests** — test full pipeline from API to output
- **pytest markers** — separate e2e tests that need Ollama from fast unit tests
- **Mocking in AI tests** — patch agent calls to test graph logic in isolation
- **What NOT to assert** — never exact LLM output, always key facts and schema
- **LLM-as-judge evaluation** — using an LLM to score another LLM's output
- **RAGAS-style metrics** — context precision, faithfulness, answer relevancy

---

## Recommended Next Project

### Build: A Personal Research Assistant with Multi-Modal RAG

**What it would be:** An agent that ingests PDFs, web pages, YouTube transcripts, and images,
then answers questions about them with citations — running fully locally.

**Why it's the right next step:**
- Builds directly on RAG skills from this project
- Adds multi-modal (text + images + audio) which this project did not cover
- Adds document loaders (PDF, HTML, YouTube) beyond plain log files
- More complex retrieval: hybrid search (semantic + keyword BM25)
- Adds a proper UI (Streamlit or Gradio) vs just CLI/API

**New AI concepts it would cover that this project did NOT:**

| Concept | What it is |
|---|---|
| **Multi-modal LLMs** | LLMs that process text + images (LLaVA, Qwen-VL) |
| **Document loaders** | Ingesting PDFs, HTML, YouTube, Notion |
| **Hybrid search** | Combining semantic (vector) + keyword (BM25) retrieval |
| **Re-ranking** | Scoring retrieved chunks by relevance before sending to LLM |
| **Query expansion** | Generating multiple search queries from one user question |
| **Conversational RAG** | Full chat interface over documents with memory |
| **Streaming** | Token-by-token streaming response in a UI |
| **Fine-tuning** | Adapting Llama to a specific domain with custom data |
| **Quantisation** | Running larger models on limited hardware (4-bit, 8-bit) |
| **Agent as API** | Exposing the agent as a proper REST service with auth |
| **Observability** | Tracing LLM calls with LangSmith or OpenTelemetry |

**Suggested stack:** Ollama + LLaVA (vision) + ChromaDB + BM25 + Streamlit + LangChain

---

*Built with Claude Code | All concepts live in `AI_LEARNINGS.md`*
