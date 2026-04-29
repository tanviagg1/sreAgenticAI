# sreAgenticAI

## Purpose
Multi-agent SRE system for learning AI engineering. Detects issues in containers, analyzes logs,
looks up runbooks, and suggests code fixes — all locally, all mocked.

## Stack
- LLM: Ollama + Llama 3.1 (local, open source, no API key)
- Orchestration: LangGraph
- RAG: ChromaDB + nomic-embed-text (local embeddings via Ollama)
- Agent Framework: LangChain
- API: FastAPI
- Tests: pytest
- UI (Phase 5): Streamlit

## Folder Structure
```
sreAgenticAI/
├── agents/         # One file per agent
├── prompts/        # All prompt templates — never inline prompts in agent code
├── skills/         # Tools agents can call (decorated with @tool)
├── mocks/          # Simulated containers, logs, runbooks
├── memory/         # Vector store and memory implementations
├── api/            # FastAPI app
├── tests/          # Unit + e2e tests (pytest)
├── AI_LEARNINGS.md # Concepts reference — read this
└── CLAUDE.md       # This file
```

## How to Run

### Prerequisites
```bash
# Install Ollama from https://ollama.com then pull models
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Install Python deps
pip install -r requirements.txt
```

### Run the API
```bash
uvicorn api.main:app --reload
```

### Run the health agent directly
```bash
python -m agents.health_agent
```

### Run tests
```bash
# Unit tests only (no LLM needed)
pytest tests/ -m "not e2e"

# All tests including e2e (requires Ollama running)
pytest tests/ -v
```

## Key Endpoints
- GET /health-check — runs health agent, returns container status report
- GET /docs — FastAPI auto-generated docs

## Conventions
- Prompts live in prompts/ — never hardcode prompts inside agent files
- Tools (skills) live in skills/ — decorated with @tool from langchain
- Mock data lives in mocks/ — never call real Docker/k8s APIs in this project
- Each phase has its own README in the repo root: README_phase1.md etc.
- AI_LEARNINGS.md is the learning reference — updated each phase

## Branch Strategy
- main: stable
- phase/1-health-agent
- phase/2-retrieval-log-agent
- phase/3-citation-rag-agent
- phase/4-coding-agent
- phase/5-orchestration
