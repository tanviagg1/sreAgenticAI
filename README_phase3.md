# Phase 3 — Citation Agent

## What you build
A Citation Agent that RAGs over SRE runbooks, searches past incident history (long-term memory),
and produces cited, authoritative recommendations with source references for every action.

## AI Concepts Introduced

| Concept | Where |
|---|---|
| Agent memory (short-term) | Conversation history in LangGraph messages list |
| Agent memory (long-term) | ChromaDB `past_incidents` collection across sessions |
| Multi-collection RAG | Separate ChromaDB collections for logs vs runbooks |
| MarkdownHeaderTextSplitter | Smart chunking by document structure |
| Source attribution / citation | Every recommendation cites runbook ID + section |
| Multi-turn conversation | Pass history across calls for follow-up questions |
| Grounding (highest level) | Recommendations ONLY from runbooks — no improvisation |

## Files Created

| File | What it teaches |
|---|---|
| `mocks/runbooks/*.md` | 5 realistic SRE runbooks with sections and IDs |
| `skills/runbook_store.py` | Runbook RAG: load, chunk by headers, embed, store, retrieve |
| `skills/citation_tools.py` | 4 citation tools including long-term memory read/write |
| `memory/incident_memory.py` | Long-term memory: store and retrieve past incidents |
| `prompts/citation_prompts.py` | Citation format, anti-hallucination rules, few-shot example |
| `agents/citation_agent.py` | Citation Agent with multi-turn support |
| `tests/test_citation_agent.py` | Tests for memory, citation, multi-turn, e2e |

## How Agent Memory Works Here

```
SHORT-TERM (within a session):
  Turn 1: "nginx is OOMKilled"
  Turn 2: "what is the long-term fix?"  <-- agent remembers Turn 1 context

  Implementation: messages list in LangGraph state — automatic

LONG-TERM (across sessions):
  Session 1: agent resolves nginx OOM, calls record_incident()
             -> stored in ChromaDB past_incidents collection

  Session 2: new nginx OOM incident
             -> agent calls search_past_incidents()
             -> retrieves INC-20260429 from last session
             -> "This happened before — here is what worked"

  Implementation: memory/incident_memory.py + ChromaDB
```

## Setup for This Phase

```bash
# Build the runbook vector store (first time only)
python -c "from skills.runbook_store import build_runbook_store; build_runbook_store()"

# Seed historical incidents into long-term memory
python -c "from memory.incident_memory import seed_past_incidents; seed_past_incidents()"

# Run the citation agent (demo: 2-turn conversation)
python -m agents.citation_agent

# Or via API
uvicorn api.main:app --reload
curl -X POST http://localhost:8000/citation \
     -H "Content-Type: application/json" \
     -d '{"symptom": "nginx OOMKilled 3 times, restart count at limit"}'
```

## Multi-turn via API

```bash
# Turn 1
curl -X POST http://localhost:8000/citation \
  -H "Content-Type: application/json" \
  -d '{"symptom": "nginx OOMKilled"}'

# Turn 2 — pass history from Turn 1
curl -X POST http://localhost:8000/citation \
  -H "Content-Type: application/json" \
  -d '{
    "symptom": "what is the long-term prevention?",
    "conversation_history": [
      {"role": "user", "content": "nginx OOMKilled"},
      {"role": "assistant", "content": "<paste Turn 1 response here>"}
    ]
  }'
```

## Running Tests

```bash
# Unit tests (no Ollama — test runbook loading, chunking, memory store/retrieve)
pytest tests/test_citation_agent.py -m "not e2e" -v

# Full suite (requires Ollama + nomic-embed-text)
pytest tests/test_citation_agent.py -v
```

## Key Learning: Source Attribution in Action

When the agent answers, look for this pattern in the output:
```
1. **Increase memory limit to 1Gi**
   Edit docker-compose.yml: memory: "1Gi"
   (Source: RB-001 - Immediate Remediation)

Similar Past Incident:
- INC-20260115: nginx — OOMKilled → increased memory limit to 1Gi
  (Source: Incident Memory)
```

Every action has a source. This is what makes the agent trustworthy.

## Runbooks Available

| ID | Title | Covers |
|---|---|---|
| RB-001 | OOMKilled | nginx OOM scenario |
| RB-002 | High CPU Usage | app-server CPU/latency scenario |
| RB-003 | Database Connection Failures | worker crash scenario |
| RB-004 | Container Restart Loop | general restart loops |
| RB-005 | SLO Breach Response | latency/error rate SLO breaches |

## Next Phase
Phase 4 adds a Coding Agent that reads code, generates fixes, and critiques its own output.
New concepts: code generation, structured output, self-reflection (agent critiques its own answer).
