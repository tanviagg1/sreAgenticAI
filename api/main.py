"""
FastAPI app — serves the health agent as an HTTP endpoint.

LEARNING — Why FastAPI?
  - Auto-generates /docs (Swagger UI) from your code — great for exploration
  - Async support — can handle multiple requests without blocking
  - Type hints become request/response validation automatically

Run with: uvicorn api.main:app --reload
Then open: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="SRE Agentic AI",
    description="Multi-agent SRE system powered by local Llama via Ollama",
    version="0.5.0 — Phase 5: Orchestrator",
)


class HealthCheckResponse(BaseModel):
    status: str
    report: str
    containers_checked: int


class LogAnalysisRequest(BaseModel):
    """
    LEARNING — Request body model:
    POST endpoints take a request body. Pydantic validates it automatically.
    If 'query' is missing or not a string, FastAPI returns a 422 error.
    """
    query: str


class LogAnalysisResponse(BaseModel):
    status: str
    report: str
    query: str


@app.get("/", summary="Root")
def root():
    return {"message": "SRE Agentic AI is running", "phase": 2, "docs": "/docs"}


@app.get(
    "/health-check",
    response_model=HealthCheckResponse,
    summary="Run the Health Agent",
    description="Triggers the ReAct health agent to check all mock containers and return a report.",
)
def health_check():
    """
    Runs the full health agent pipeline:
    1. Agent calls tools to check container statuses
    2. Agent reasons about issues using the ReAct loop
    3. Agent produces a structured health report
    """
    try:
        # Import here to avoid loading the LLM at startup
        from agents.health_agent import run_health_check
        from mocks.containers import MOCK_CONTAINERS

        result = run_health_check()

        return HealthCheckResponse(
            status="ok",
            report=result["output"],
            containers_checked=len(MOCK_CONTAINERS),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


class CitationRequest(BaseModel):
    """
    LEARNING — Optional conversation_history field:
    Allows callers to pass prior conversation turns for multi-turn support.
    Each turn is {"role": "user"|"assistant", "content": "..."}.
    """
    symptom: str
    conversation_history: list[dict] = []


class CitationResponse(BaseModel):
    status: str
    report: str
    symptom: str


@app.post(
    "/citation",
    response_model=CitationResponse,
    summary="Run the Citation Agent",
    description="Searches runbooks and past incidents, returns cited recommendations.",
)
def citation(request: CitationRequest):
    """
    LEARNING — Citation endpoint with multi-turn support:
    Pass conversation_history to continue a previous conversation.
    The agent will remember previous questions and build on them.

    Try:
      {"symptom": "nginx is OOMKilled, restart count is 3"}
      {"symptom": "worker keeps crashing with exit code 1"}
      {"symptom": "app-server CPU at 95%, SLO breach on latency"}
    """
    try:
        from agents.citation_agent import run_citation_query
        result = run_citation_query(
            request.symptom,
            conversation_history=request.conversation_history or None,
        )
        return CitationResponse(
            status="ok",
            report=result["output"],
            symptom=request.symptom,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


class CodeFixRequest(BaseModel):
    """
    LEARNING — auto_approve field:
    In production this would default to False — human must approve via a separate call.
    Set to True only in testing or demo mode to skip the interactive prompt.
    """
    service_name: str
    problem: str
    auto_approve: bool = False


class CodeFixResponse(BaseModel):
    status: str
    service_name: str
    fix: dict | None
    reflection: dict | None
    revision_count: int


@app.post(
    "/fix-code",
    response_model=CodeFixResponse,
    summary="Run the Coding Agent",
    description="Generates a config fix with self-reflection and human-in-the-loop approval.",
)
def fix_code(request: CodeFixRequest):
    """
    LEARNING — Code generation pipeline:
    1. Agent reads service config via tools (grounded generation)
    2. Agent generates a structured JSON fix
    3. Second LLM call critiques the fix (self-reflection)
    4. If confidence >= 7: presented for human approval (or auto-approved in test mode)

    Try:
      {"service_name": "nginx", "problem": "nginx OOMKilled, memory limit too low", "auto_approve": true}
      {"service_name": "worker", "problem": "worker crashes with no DB retry logic", "auto_approve": true}
    """
    try:
        from agents.coding_agent import run_coding_agent
        result = run_coding_agent(
            service_name=request.service_name,
            problem_description=request.problem,
            auto_approve=request.auto_approve,
        )
        return CodeFixResponse(
            status=result["status"],
            service_name=request.service_name,
            fix=result.get("fix"),
            reflection=result.get("reflection"),
            revision_count=result.get("revision_count", 0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


class PipelineRequest(BaseModel):
    """
    LEARNING — Orchestrator request:
    A single incident description triggers the full multi-agent graph.
    require_human_approval=False is safe for API/test use.
    Set to True in production to gate the coding agent fix.
    """
    incident_description: str
    require_human_approval: bool = False


class PipelineResponse(BaseModel):
    overall_status: str
    unhealthy_services: list[str]
    steps_taken: list[str]
    final_summary: str
    fix_approved: bool


@app.post(
    "/run-pipeline",
    response_model=PipelineResponse,
    summary="Run the full SRE orchestration pipeline",
    description="Runs Health -> Retrieval -> Citation -> Coding agents via LangGraph.",
)
def run_pipeline(request: PipelineRequest):
    """
    LEARNING — The full multi-agent graph endpoint:
    One call triggers the entire SRE pipeline:
    1. Health Agent checks all containers
    2. If issues found: Retrieval Agent searches logs
    3. Citation Agent looks up runbooks
    4. Coding Agent generates a fix
    5. (Optional) Human approval gate
    6. Summary synthesises everything

    Try:
      {"incident_description": "nginx OOMKilled 3 times, worker stopped"}
    """
    try:
        from agents.orchestrator import run_sre_pipeline
        final_state = run_sre_pipeline(
            incident_description=request.incident_description,
            require_human_approval=request.require_human_approval,
        )
        return PipelineResponse(
            overall_status=final_state.get("overall_status", ""),
            unhealthy_services=final_state.get("unhealthy_services", []),
            steps_taken=final_state.get("steps_taken", []),
            final_summary=final_state.get("final_summary", ""),
            fix_approved=final_state.get("fix_approved", False),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@app.post(
    "/log-analysis",
    response_model=LogAnalysisResponse,
    summary="Run the Retrieval Agent",
    description="Semantically searches log files and returns a grounded analysis report.",
)
def log_analysis(request: LogAnalysisRequest):
    """
    LEARNING — RAG endpoint:
    1. Query is embedded and used to search ChromaDB
    2. Relevant log chunks are retrieved
    3. LLM synthesizes a grounded answer from the chunks
    4. Response includes source citations

    Try queries like:
      {"query": "Why did the worker stop?"}
      {"query": "Find all OOM errors"}
      {"query": "What was the CPU situation on app-server?"}
    """
    try:
        from agents.retrieval_agent import run_log_analysis
        result = run_log_analysis(request.query)
        return LogAnalysisResponse(
            status="ok",
            report=result["output"],
            query=request.query,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
