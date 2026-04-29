# SRE Agentic AI

A multi-agent SRE system built for learning AI engineering.
Runs fully locally using open-source tools — no API keys, no cloud.

## What it does

Simulates an SRE on-call workflow:
1. Detects unhealthy containers (Health Agent)
2. Searches and analyzes logs (Retrieval Agent — Phase 2)
3. Looks up runbooks and past incidents (Citation Agent — Phase 3)
4. Suggests and applies code fixes (Coding Agent — Phase 4)
5. Orchestrates all agents intelligently (Orchestrator — Phase 5)

## Stack

| Layer | Tool |
|---|---|
| LLM | Ollama + Llama 3.1 (local) |
| Orchestration | LangGraph |
| RAG | ChromaDB + nomic-embed-text |
| Agent Framework | LangChain |
| API | FastAPI |
| Tests | pytest |

## Quick Start

### 1. Install Ollama and pull models
```bash
# Install from https://ollama.com
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

### 2. Install Python dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up environment
```bash
cp .env.example .env
```

### 4. Run the API
```bash
uvicorn api.main:app --reload
# Open http://localhost:8000/docs
```

### 5. Or run the agent directly
```bash
python -m agents.health_agent
```

## Testing

```bash
# Unit tests only — fast, no Ollama needed
pytest tests/ -m "not e2e" -v

# All tests including e2e — requires Ollama running
pytest tests/ -v
```

## Learning Resources

- `AI_LEARNINGS.md` — comprehensive reference for every AI concept used
- `README_phase1.md` — Phase 1 deep dive

## Project Structure

```
sreAgenticAI/
├── agents/         # One agent per file
├── prompts/        # All prompt templates
├── skills/         # Tools agents can call (@tool decorated)
├── mocks/          # Simulated containers, logs, runbooks
├── api/            # FastAPI app
├── tests/          # Unit + integration + e2e tests
├── AI_LEARNINGS.md # AI concept reference
└── CLAUDE.md       # Project context for Claude Code
```

## Phases

| Phase | Branch | Status |
|---|---|---|
| 1 — Health Agent | phase/1-health-agent | In progress |
| 2 — Retrieval + Log Agent | phase/2-retrieval-log-agent | Planned |
| 3 — Citation + RAG Agent | phase/3-citation-rag-agent | Planned |
| 4 — Coding Agent | phase/4-coding-agent | Planned |
| 5 — Orchestration | phase/5-orchestration | Planned |
