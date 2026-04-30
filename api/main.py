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
    version="0.2.0 — Phase 2: Retrieval Agent",
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
