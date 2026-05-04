# Phase 4 — Coding Agent

## What you build
A Coding Agent that reads service configs, generates precise structured fixes,
critiques its own output (self-reflection), and requires human approval before
any fix is considered applied.

## AI Concepts Introduced

| Concept | Where |
|---|---|
| Code generation | `agents/coding_agent.py` — LLM generates config fixes |
| Structured output | `prompts/coding_prompts.py` — LLM forced to respond in JSON schema |
| Self-reflection | `agents/coding_agent.py:reflect_on_fix()` — second LLM call critiques first |
| Generate → critique → revise loop | `run_coding_agent()` — up to 2 revision passes |
| Human-in-the-loop | `run_coding_agent()` — approval gate before fix is applied |
| Grounded code generation | Tools read real config before LLM generates fix |

## Files Created

| File | What it teaches |
|---|---|
| `mocks/services/nginx_config.py` | Mock service configs with intentional bugs |
| `prompts/coding_prompts.py` | Structured output schema, self-reflection prompt |
| `skills/code_tools.py` | Read configs, detect issues, validate fix schema |
| `agents/coding_agent.py` | Full pipeline: generate → reflect → revise → approve |
| `tests/test_coding_agent.py` | Schema validation, reflection quality, full e2e |
| `POST /fix-code` | API endpoint for the coding agent |

## How Self-Reflection Works

```
PASS 1 — Generation
  Agent reads nginx config via tools
  Agent generates fix JSON: {"fixed": "memory_limit: 1Gi", ...}

PASS 2 — Reflection (separate LLM call)
  "Here is the fix. Does it solve the OOM problem?
   Any new risks? Confidence 1-10."
  -> {"confidence_score": 8, "approved": true, "new_risks": [...]}

DECISION
  confidence >= 7 AND approved=true -> show to human for approval
  otherwise -> revise and retry (max 2 revisions)

HUMAN GATE
  Human sees: file, original, fixed, explanation, risk_level
  Types: yes/no
  Only "yes" proceeds
```

## Setup for This Phase

```bash
# No new models needed — uses llama3.1:8b and existing deps

# Run the coding agent (interactive — will ask for approval)
python -m agents.coding_agent

# Or via API (auto_approve=true skips the interactive prompt)
uvicorn api.main:app --reload

curl -X POST http://localhost:8000/fix-code \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "nginx",
    "problem": "nginx OOMKilled repeatedly, memory_limit of 512Mi is too low",
    "auto_approve": true
  }'
```

## Running Tests

```bash
# Unit tests — no LLM (config reading, issue detection, schema validation)
pytest tests/test_coding_agent.py -m "not e2e" -v

# Full suite with LLM
pytest tests/test_coding_agent.py -v
```

## Key Learning: Structured Output

The most important thing to notice when running this phase:

The LLM does NOT return free text like "You should increase the memory limit".
It returns structured JSON:
```json
{
  "file": "docker-compose.yml",
  "change_type": "modify",
  "problem_summary": "memory_limit 512Mi equals peak nginx usage — causes OOMKilled",
  "original": "memory_limit: 512Mi",
  "fixed": "memory_limit: 1Gi",
  "explanation": "Doubles the limit giving 100% headroom above current peak usage",
  "risk_level": "low",
  "side_effects": ["increased memory cost per container"]
}
```

This JSON can be:
- Validated programmatically (is the fix well-formed?)
- Passed to another agent (e.g. the orchestrator in Phase 5)
- Applied automatically to a real file
- Displayed in a UI with proper formatting

Structured output is what makes LLM output machine-usable.

## Known Issues in Mock Configs

| Service | Bug | Suggested Fix |
|---|---|---|
| nginx | memory_limit=512Mi (too low) | Increase to 1Gi, add alert at 80% |
| worker | No DB_RETRY_ATTEMPTS, no DB_CONNECT_TIMEOUT | Add retry logic env vars |
| app-server | replicas=1, no REQUEST_TIMEOUT_MS | Add autoscaling, add timeout |

## Next Phase
Phase 5 wires all agents together with a LangGraph orchestrator.
New concepts: stateful graphs, conditional routing, supervisor pattern, LLM evaluation.
