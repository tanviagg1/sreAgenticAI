# Phase 1 — Health Agent

## What you build
A ReAct agent that checks mock container health using a local Llama model and reports issues.

## AI Concepts Introduced
- Prompt engineering (system prompts, chain-of-thought, structured output)
- Tool use / function calling
- The ReAct pattern (Reason + Act loop)
- LLM temperature
- Prompt templates

## Files Created

| File | What it teaches |
|---|---|
| `mocks/containers.py` | How to mock infrastructure data for testing |
| `prompts/health_prompts.py` | System prompts, few-shot, chain-of-thought |
| `skills/container_health.py` | @tool decorator, docstring-as-description |
| `agents/health_agent.py` | ReAct agent setup, AgentExecutor, ChatOllama |
| `api/main.py` | FastAPI, Pydantic response models |
| `tests/test_health_agent.py` | Unit, integration, e2e test layers |

## How the ReAct Loop Works

```
Input: "Check all containers and report issues"
         |
Thought: "I should get an overview first"
Action:  get_system_summary()
Obs:     {"overall_status": "CRITICAL", "healthy": 2, "unhealthy": 3}
         |
Thought: "Critical — I need details on unhealthy ones"
Action:  get_unhealthy_containers()
Obs:     [worker(stopped), nginx(OOMKilled), app-server(degraded)]
         |
Thought: "I have enough to write a full report"
Final Answer: ## System Status: CRITICAL ...
```

## Setup for This Phase

```bash
# 1. Make sure Ollama is running
ollama serve

# 2. Pull the model if not already done
ollama pull llama3.1:8b

# 3. Install deps
pip install -r requirements.txt

# 4. Run the agent directly (watch the ReAct loop in the terminal)
python -m agents.health_agent

# 5. Or via the API
uvicorn api.main:app --reload
curl http://localhost:8000/health-check
```

## Running Tests

```bash
# Fast unit tests (no Ollama needed)
pytest tests/test_health_agent.py -m "not e2e" -v

# Full test suite including e2e (Ollama must be running)
pytest tests/test_health_agent.py -v
```

## What to Look For When Running

When you run `python -m agents.health_agent`, watch the terminal output.
You will see the ReAct loop printed live:

```
> Entering new AgentExecutor chain...
Thought: I need to check the overall system health first.
Action: get_system_summary
Action Input: {}
Observation: {"overall_status": "CRITICAL", ...}
Thought: The system is critical. Let me get details on unhealthy containers.
Action: get_unhealthy_containers
...
Final Answer: ## System Status: CRITICAL
...
> Finished chain.
```

This is the Thought -> Action -> Observation loop in action.

## What is Mocked vs What Would Be Real

| Mock | Real equivalent |
|---|---|
| `mocks/containers.py` | Docker SDK / kubectl / Prometheus |
| Static container data | Live metrics from container runtime |
| In-memory data | Redis / time-series DB |

## Next Phase
Phase 2 adds a Retrieval Agent that searches mock log files using RAG and ChromaDB.
You will learn: vector embeddings, semantic search, chunking strategies.
