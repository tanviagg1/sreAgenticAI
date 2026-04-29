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
    version="0.1.0 — Phase 1: Health Agent",
)


class HealthCheckResponse(BaseModel):
    """
    LEARNING — Pydantic models:
    Define the shape of API responses. FastAPI validates and serializes automatically.
    This is also self-documenting — appears in /docs.
    """
    status: str
    report: str
    containers_checked: int


@app.get("/", summary="Root")
def root():
    return {"message": "SRE Agentic AI is running", "phase": 1, "docs": "/docs"}


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
        # LEARNING: In production, never expose raw exception messages to clients.
        # Log them server-side and return a generic error.
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
