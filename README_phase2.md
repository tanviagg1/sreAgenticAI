# Phase 2 — Retrieval Log Agent

## What you build
A RAG-powered agent that semantically searches mock log files using ChromaDB
and produces grounded, cited log analysis reports.

## AI Concepts Introduced
- RAG (Retrieval Augmented Generation)
- Vector embeddings and semantic search
- ChromaDB as a local vector database
- Chunking strategies (RecursiveCharacterTextSplitter)
- Document metadata and source citation
- Grounding — preventing hallucination by anchoring answers in retrieved data
- Relevance scoring (cosine distance)

## Files Created

| File | What it teaches |
|---|---|
| `mocks/logs/*.log` | Realistic SRE log data for 5 services |
| `skills/vector_store.py` | Full RAG pipeline: load, chunk, embed, store, retrieve |
| `skills/log_search.py` | @tool wrappers for semantic and keyword log search |
| `prompts/retrieval_prompts.py` | Grounding rules, anti-hallucination prompts |
| `agents/retrieval_agent.py` | RAG agent using ChromaDB tools |
| `tests/test_retrieval_agent.py` | Unit, integration, e2e tests for RAG |

## How RAG Works Here

```
Query: "Why did the worker stop?"
         |
Step 1: Embed query -> [0.23, -0.81, 0.44, ...] (768 dimensions)
         |
Step 2: ChromaDB finds closest log chunks by vector similarity
         |
Step 3: Top-5 chunks returned (worker.log entries about DB connection failures)
         |
Step 4: LLM receives: query + retrieved chunks
         |
Step 5: LLM produces grounded answer citing worker.log timestamps
```

## Setup for This Phase

```bash
# Pull the embedding model (if not done)
ollama pull nomic-embed-text

# Install new deps
pip install -r requirements.txt

# Build the vector store (first time only — takes ~30s)
python -c "from skills.vector_store import build_vector_store; build_vector_store()"

# Run the retrieval agent
python -m agents.retrieval_agent

# Or via API
uvicorn api.main:app --reload
curl -X POST http://localhost:8000/log-analysis \
     -H "Content-Type: application/json" \
     -d '{"query": "Why did the worker stop?"}'
```

## Running Tests

```bash
# Unit tests — no Ollama needed (log loading, chunking, error counting)
pytest tests/test_retrieval_agent.py -m "not e2e" -v

# Full suite — requires Ollama + nomic-embed-text running
pytest tests/test_retrieval_agent.py -v
```

## Key Learning: Semantic vs Keyword Search

Run this to see the difference:
```python
from skills.log_search import search_logs_semantic

# Semantic — finds OOMKilled even though query says "out of memory"
results = search_logs_semantic.invoke({"query": "out of memory errors"})
print([r["service"] for r in results])  # includes nginx

# This would FAIL with keyword search because "out of memory" != "OOMKilled"
```

## Mock Log Scenarios

| Service | Issue in logs |
|---|---|
| nginx | 3x OOMKilled (memory growing to 512MB limit) |
| worker | Fatal crash due to postgres connection refused |
| app-server | CPU at 95%, SLO breach on latency and error rate |
| postgres | Connection limit reached (100/100), then recovered |
| redis | Healthy — no errors |

## Next Phase
Phase 3 adds a Citation Agent that RAGs over SRE runbooks to provide
authoritative recommendations alongside log evidence.
New concepts: agent memory, long-term vector store, source attribution.
