"""
Orchestrator — Phase 5.

LEARNING — LangGraph StateGraph:

All previous phases had standalone agents. Phase 5 wires them into a
directed graph where:
  - Each agent is a NODE
  - Connections between agents are EDGES
  - Data flows through a shared STATE object
  - The graph decides which node to visit next using CONDITIONAL EDGES

LEARNING — Supervisor Pattern:
The orchestrator is a "supervisor" agent. It:
  1. Reads the current state
  2. Decides which specialist agent to call next
  3. Routes to that agent
  4. Repeats until the task is complete

This is different from a pipeline (fixed order) — the supervisor can
choose different paths depending on what it finds:

  Health check → CRITICAL?
    YES → Retrieval → Citation → Coding → Human approval
    NO  → Done (healthy system, no action needed)

LEARNING — Shared State (TypedDict):
All nodes read from and write to a single state dict.
TypedDict gives it a schema so every field is typed.
Each agent adds its output to the state — later agents can see earlier results.

LEARNING — Human-in-the-Loop with LangGraph interrupt:
LangGraph supports pausing a graph mid-execution.
We pause BEFORE applying any code fix — the graph freezes,
waits for external input (human approval), then resumes.
"""

import os
from typing import TypedDict, Annotated, Literal
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()


# =============================================================================
# LEARNING — Shared State Schema (TypedDict)
# Every node reads from and writes to this state.
# Fields accumulate as the graph runs — later nodes see earlier results.
# =============================================================================

class SREState(TypedDict):
    # Input
    trigger: str                    # What kicked off this run ("alert", "manual", "scheduled")
    incident_description: str       # Plain English description of the issue

    # Health Agent output
    health_report: str              # Full health report text
    overall_status: str             # "HEALTHY" | "DEGRADED" | "CRITICAL"
    unhealthy_services: list[str]   # Names of services with issues

    # Retrieval Agent output
    log_analysis: str               # Log analysis report text
    log_evidence: list[str]         # Key log lines found

    # Citation Agent output
    runbook_recommendations: str    # Cited runbook recommendations
    recommended_actions: list[str]  # Extracted action items

    # Coding Agent output
    proposed_fix: dict              # The CodeFix JSON
    fix_reflection: dict            # The self-reflection result
    fix_approved: bool              # Whether human approved the fix

    # Orchestrator tracking
    current_step: str               # Which node is currently running
    steps_taken: list[str]          # Audit log of all steps taken
    final_summary: str              # End-to-end incident summary


# =============================================================================
# GRAPH NODES — Each is a function that takes state, does work, returns updates
# =============================================================================

def health_check_node(state: SREState) -> dict:
    """
    Node 1: Run the Health Agent.

    LEARNING — Node signature:
    Every LangGraph node takes the full state and returns a dict
    of ONLY the fields it wants to update. LangGraph merges the
    returned dict into the current state automatically.
    """
    print("\n[ORCHESTRATOR] Running Health Agent...")
    from agents.health_agent import run_health_check
    from skills.container_health import get_system_summary, get_unhealthy_containers

    result = run_health_check()
    health_report = result["output"]

    # Extract structured data from tools directly (deterministic, no LLM needed)
    summary = get_system_summary.invoke({})
    unhealthy = get_unhealthy_containers.invoke({})
    unhealthy_names = [c["name"] for c in unhealthy]

    return {
        "health_report": health_report,
        "overall_status": summary["overall_status"],
        "unhealthy_services": unhealthy_names,
        "current_step": "health_check",
        "steps_taken": state.get("steps_taken", []) + ["health_check"],
    }


def log_retrieval_node(state: SREState) -> dict:
    """
    Node 2: Run the Retrieval Agent on the unhealthy services found in Node 1.

    LEARNING — State-driven queries:
    The retrieval query is built from what the health agent found.
    This is how agents collaborate — each node's output informs the next node's input.
    """
    print("\n[ORCHESTRATOR] Running Retrieval Agent...")
    from agents.retrieval_agent import run_log_analysis

    services = state.get("unhealthy_services", [])
    query = f"Find errors and root causes for these services: {', '.join(services)}. {state.get('incident_description', '')}"

    result = run_log_analysis(query)

    return {
        "log_analysis": result["output"],
        "current_step": "log_retrieval",
        "steps_taken": state.get("steps_taken", []) + ["log_retrieval"],
    }


def citation_node(state: SREState) -> dict:
    """
    Node 3: Run the Citation Agent using log evidence from Node 2.

    LEARNING — Chaining context:
    We pass BOTH the original incident description AND the log analysis
    as context to the citation agent. This grounds its runbook search
    in what was actually found, not just the original symptom.
    """
    print("\n[ORCHESTRATOR] Running Citation Agent...")
    from agents.citation_agent import run_citation_query

    symptom = f"""
Incident: {state.get('incident_description', '')}
Health status: {state.get('overall_status')}
Affected services: {', '.join(state.get('unhealthy_services', []))}
Log evidence: {state.get('log_analysis', '')[:500]}
"""
    result = run_citation_query(symptom)

    # Extract recommended actions as a list for the coding agent to act on
    lines = result["output"].split("\n")
    actions = [l.strip() for l in lines if l.strip().startswith(("1.", "2.", "3.", "-", "•"))]

    return {
        "runbook_recommendations": result["output"],
        "recommended_actions": actions[:5],  # top 5 actions
        "current_step": "citation",
        "steps_taken": state.get("steps_taken", []) + ["citation"],
    }


def coding_node(state: SREState) -> dict:
    """
    Node 4: Run the Coding Agent on the most critical unhealthy service.

    LEARNING — Human-in-the-loop via auto_approve=False:
    The coding agent will pause and ask for human input.
    In the graph version, we use auto_approve=True and implement
    the approval gate as a separate LangGraph interrupt node instead,
    so the graph controls the pause point explicitly.
    """
    print("\n[ORCHESTRATOR] Running Coding Agent...")
    from agents.coding_agent import run_coding_agent

    # Target the first (most severe) unhealthy service
    services = state.get("unhealthy_services", [])
    if not services:
        return {
            "proposed_fix": {},
            "fix_approved": False,
            "current_step": "coding",
            "steps_taken": state.get("steps_taken", []) + ["coding_skipped"],
        }

    target_service = services[0]
    problem = f"{state.get('incident_description', '')} — service: {target_service}"

    # auto_approve=True because the graph handles human-in-the-loop separately
    result = run_coding_agent(
        service_name=target_service,
        problem_description=problem,
        auto_approve=True,
    )

    return {
        "proposed_fix": result.get("fix", {}),
        "fix_reflection": result.get("reflection", {}),
        "fix_approved": False,  # starts as False — set to True after human approval node
        "current_step": "coding",
        "steps_taken": state.get("steps_taken", []) + ["coding"],
    }


def human_approval_node(state: SREState) -> dict:
    """
    Node 5: Human-in-the-loop approval gate.

    LEARNING — Human-in-the-loop in LangGraph:
    This node pauses the graph and presents the fix to a human.
    In a real system, LangGraph's interrupt() would freeze the graph
    and wait for an external event (Slack button, webhook, UI action).

    Here we implement it as an interactive terminal prompt for learning.
    The graph only proceeds to the summary node after this node runs.
    """
    print("\n[ORCHESTRATOR] ⚠️  Human approval required")
    fix = state.get("proposed_fix", {})

    if not fix or "parse_error" in fix:
        print("No valid fix to approve.")
        return {
            "fix_approved": False,
            "current_step": "human_approval",
            "steps_taken": state.get("steps_taken", []) + ["human_approval_skipped"],
        }

    print("\n" + "=" * 60)
    print("PROPOSED FIX — Review and approve")
    print("=" * 60)
    print(f"Service:     {state.get('unhealthy_services', ['unknown'])[0]}")
    print(f"Problem:     {fix.get('problem_summary', 'N/A')}")
    print(f"Risk:        {fix.get('risk_level', 'N/A')}")
    print(f"Original:    {fix.get('original', 'N/A')}")
    print(f"Fixed:       {fix.get('fixed', 'N/A')}")
    print(f"Explanation: {fix.get('explanation', 'N/A')}")
    confidence = state.get("fix_reflection", {}).get("confidence_score", "N/A")
    print(f"Confidence:  {confidence}/10")
    print("=" * 60)

    response = input("\nApply this fix? (yes/no): ").strip().lower()
    approved = response in ("yes", "y")

    return {
        "fix_approved": approved,
        "current_step": "human_approval",
        "steps_taken": state.get("steps_taken", []) + [f"human_approval({'approved' if approved else 'rejected'})"],
    }


def summary_node(state: SREState) -> dict:
    """
    Node 6: Generate a final incident summary using the LLM.

    LEARNING — End-of-graph synthesis:
    The summary node is the final node. It has access to ALL previous
    agent outputs in the state and synthesises them into one report.
    This is the power of shared state — every node's work is visible here.
    """
    print("\n[ORCHESTRATOR] Generating final summary...")
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    prompt = f"""Summarise this SRE incident response in a concise executive report.

Health Status: {state.get('overall_status')}
Affected Services: {', '.join(state.get('unhealthy_services', []))}
Steps Taken: {' -> '.join(state.get('steps_taken', []))}
Fix Approved: {state.get('fix_approved')}
Fix Applied: {state.get('proposed_fix', {}).get('problem_summary', 'None')}

Write a 3-paragraph report:
1. What happened (based on health and log findings)
2. What was recommended (based on runbooks)
3. What action was taken (fix approved/rejected and next steps)
"""
    response = llm.invoke([HumanMessage(content=prompt)])

    return {
        "final_summary": response.content,
        "current_step": "summary",
        "steps_taken": state.get("steps_taken", []) + ["summary"],
    }


# =============================================================================
# LEARNING — Conditional Routing Functions
# These are plain Python functions that read state and return the NEXT NODE NAME.
# LangGraph calls these at each conditional edge to decide where to go.
# =============================================================================

def route_after_health(state: SREState) -> Literal["log_retrieval", "summary"]:
    """
    After health check: if system is healthy, skip to summary.
    If DEGRADED or CRITICAL, run the full pipeline.

    LEARNING — Conditional edge:
    This function returns the NAME of the next node as a string.
    LangGraph uses the return value to pick the next edge to follow.
    """
    status = state.get("overall_status", "HEALTHY")
    if status == "HEALTHY":
        print("[ORCHESTRATOR] System healthy — skipping to summary")
        return "summary"
    return "log_retrieval"


def route_after_citation(state: SREState) -> Literal["coding", "summary"]:
    """
    After citation: only run the coding agent if there are unhealthy services
    with fixable configs. Otherwise go straight to summary.
    """
    from mocks.services.nginx_config import NGINX_SERVICE_CONFIG
    fixable = {"nginx", "worker", "app-server"}
    unhealthy = set(state.get("unhealthy_services", []))

    if unhealthy & fixable:
        return "coding"
    return "summary"


# =============================================================================
# LEARNING — Building the StateGraph
# Nodes + edges + conditional edges = the complete agent graph
# =============================================================================

def build_sre_graph(require_human_approval: bool = True):
    """
    Assemble the full SRE orchestration graph.

    LEARNING — StateGraph construction:
    1. Create graph with state schema
    2. Add nodes (functions)
    3. Set entry point
    4. Add edges (fixed) and conditional edges (dynamic)
    5. Compile — produces a runnable graph

    LEARNING — MemorySaver (checkpointer):
    Saves graph state at each step. Enables:
    - Resuming after interruption
    - Inspecting what each node produced
    - Replaying a run from any checkpoint
    """
    graph = StateGraph(SREState)

    # Add all nodes
    graph.add_node("health_check", health_check_node)
    graph.add_node("log_retrieval", log_retrieval_node)
    graph.add_node("citation", citation_node)
    graph.add_node("coding", coding_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("summary", summary_node)

    # Entry point
    graph.set_entry_point("health_check")

    # LEARNING — Conditional edge after health check:
    # Route to log_retrieval if issues found, summary if all healthy
    graph.add_conditional_edges(
        "health_check",
        route_after_health,
        {"log_retrieval": "log_retrieval", "summary": "summary"},
    )

    # Fixed edges: retrieval always leads to citation
    graph.add_edge("log_retrieval", "citation")

    # LEARNING — Conditional edge after citation:
    # Only run coding agent if there are fixable services
    graph.add_conditional_edges(
        "citation",
        route_after_citation,
        {"coding": "coding", "summary": "summary"},
    )

    # After coding: human approval (if required) or straight to summary
    if require_human_approval:
        graph.add_edge("coding", "human_approval")
        graph.add_edge("human_approval", "summary")
    else:
        graph.add_edge("coding", "summary")

    # Summary always ends the graph
    graph.add_edge("summary", END)

    # LEARNING — Compile with MemorySaver:
    # The checkpointer saves state at each step for inspection/resume
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def run_sre_pipeline(incident_description: str, require_human_approval: bool = True) -> SREState:
    """
    Run the full SRE orchestration pipeline for a given incident.

    LEARNING — thread_id in LangGraph:
    Each run gets a unique thread_id. This lets MemorySaver store
    multiple independent runs without them interfering.
    You can later retrieve a past run's state using its thread_id.
    """
    graph = build_sre_graph(require_human_approval=require_human_approval)

    initial_state: SREState = {
        "trigger": "manual",
        "incident_description": incident_description,
        "health_report": "",
        "overall_status": "",
        "unhealthy_services": [],
        "log_analysis": "",
        "log_evidence": [],
        "runbook_recommendations": "",
        "recommended_actions": [],
        "proposed_fix": {},
        "fix_reflection": {},
        "fix_approved": False,
        "current_step": "start",
        "steps_taken": [],
        "final_summary": "",
    }

    config = {"configurable": {"thread_id": "sre-run-1"}}

    print("\n" + "=" * 60)
    print("SRE ORCHESTRATOR STARTING")
    print("=" * 60)
    print(f"Incident: {incident_description}\n")

    final_state = graph.invoke(initial_state, config=config)

    print("\n" + "=" * 60)
    print("FINAL INCIDENT SUMMARY")
    print("=" * 60)
    print(final_state["final_summary"])
    print(f"\nSteps taken: {' -> '.join(final_state['steps_taken'])}")

    return final_state


if __name__ == "__main__":
    run_sre_pipeline(
        incident_description="nginx is OOMKilled with restart count 3. Worker container stopped.",
        require_human_approval=True,
    )
