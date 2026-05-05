# Phase 5 — LangGraph Orchestrator

## What you build
A LangGraph StateGraph that wires all 4 agents into a single coordinated pipeline.
One incident description triggers the full flow: detect → investigate → recommend → fix → summarise.

## AI Concepts Introduced

| Concept | Where |
|---|---|
| LangGraph StateGraph | `agents/orchestrator.py` — graph with nodes, edges, state |
| Shared state (TypedDict) | `SREState` — all agents read/write one dict |
| Supervisor pattern | Orchestrator decides which agent runs next |
| Conditional edges | `route_after_health`, `route_after_citation` — dynamic routing |
| Human-in-the-loop (graph) | `human_approval_node` — graph pauses for human input |
| MemorySaver checkpointer | State saved at every step — resumable runs |
| LLM-as-judge evaluation | `skills/evaluator.py` — LLM scores the pipeline output |
| RAG evaluation (RAGAS-style) | `evaluate_rag_retrieval` — precision, faithfulness, relevancy |

## How the Graph Works

```
START
  |
health_check ──── HEALTHY ──────────────────────────────┐
  |                                                      |
CRITICAL/DEGRADED                                        |
  |                                                      |
log_retrieval                                            |
  |                                                      |
citation ──── no fixable services ──────────────────────┤
  |                                                      |
coding                                                   |
  |                                                      |
human_approval (optional)                                |
  |                                                      |
summary ◄────────────────────────────────────────────────┘
  |
END
```

## Files Created

| File | What it teaches |
|---|---|
| `agents/orchestrator.py` | StateGraph, nodes, edges, conditional routing, MemorySaver |
| `prompts/orchestrator_prompts.py` | Summary prompt, LLM-eval prompt |
| `skills/evaluator.py` | LLM-as-judge, RAGAS-style metrics |
| `tests/test_orchestrator.py` | Routing tests, node mocking, full e2e |
| `POST /run-pipeline` | Single endpoint for the full multi-agent graph |

## Setup for This Phase

```bash
# No new models or deps needed

# Run the full orchestrator (interactive — will ask for fix approval)
python -m agents.orchestrator

# Or via API (no human prompt)
uvicorn api.main:app --reload

curl -X POST http://localhost:8000/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "incident_description": "nginx is OOMKilled, worker stopped",
    "require_human_approval": false
  }'
```

## Running Tests

```bash
# Unit tests — no LLM (routing logic, graph structure, node mocking)
pytest tests/test_orchestrator.py -m "not e2e" -v

# Full suite with LLM
pytest tests/test_orchestrator.py -v

# Run all phases together
pytest tests/ -m "not e2e" -v
```

## Key Learning: Shared State

The most important concept in Phase 5 is the `SREState` TypedDict.
Watch how each node adds to it:

```
After health_check:
  state["overall_status"] = "CRITICAL"
  state["unhealthy_services"] = ["nginx", "worker"]

After log_retrieval:
  state["log_analysis"] = "nginx OOM at 09:22..."

After citation:
  state["runbook_recommendations"] = "Per RB-001, increase memory to 1Gi..."

After coding:
  state["proposed_fix"] = {"fixed": "memory_limit: 1Gi", ...}

After summary:
  state["final_summary"] = "nginx OOMKilled due to 512Mi limit. Fix approved."
```

Every node's output is visible to every subsequent node.
The summary node can see everything — that's how it produces a coherent report.

## All API Endpoints (complete system)

| Method | Endpoint | Agent | Phase |
|---|---|---|---|
| GET | /health-check | Health Agent | 1 |
| POST | /log-analysis | Retrieval Agent | 2 |
| POST | /citation | Citation Agent | 3 |
| POST | /fix-code | Coding Agent | 4 |
| POST | /run-pipeline | Orchestrator (all agents) | 5 |
| GET | /docs | Swagger UI | All |

## LLM Evaluation

After running the pipeline, evaluate quality:

```python
from skills.evaluator import evaluate_pipeline_output
scores = evaluate_pipeline_output(final_state)
print(scores)
# {"faithfulness": 4, "completeness": 5, "actionability": 3, "overall": 4, ...}
```

Scores are 1-5. Use these to track quality over time as you change prompts or models.
