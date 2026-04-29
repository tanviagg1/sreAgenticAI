"""
Container health skills — tools the Health Agent can call.

LEARNING — Tool Use / Function Calling:

The @tool decorator from LangChain does two things:
  1. Wraps your Python function so the LLM can call it
  2. Uses the function NAME and DOCSTRING as the tool description

The LLM reads the docstring to decide WHEN to call each tool.
Write docstrings as if explaining to a colleague what the function does.
Clear docstrings = better tool selection by the LLM.

IMPORTANT: Tools should be pure functions — no side effects, no state.
The agent calls them, gets the result, and uses it to reason further.

In a real system these would call:
  - Docker SDK: client.containers.get(name).status
  - Kubernetes API: v1.read_namespaced_pod_status(...)
  - Prometheus: query metrics endpoint
"""

from langchain.tools import tool
from mocks.containers import MOCK_CONTAINERS, SEVERITY_RANK


@tool
def list_all_containers() -> list[str]:
    """
    List the names of all containers in the system.
    Call this first to know which containers exist before checking individual ones.
    """
    return list(MOCK_CONTAINERS.keys())


@tool
def check_container_health(container_name: str) -> dict:
    """
    Check the health status of a specific container by name.
    Returns status, reason for any issue, CPU usage, memory usage, and restart count.
    Use this to get details on a specific container after listing them.
    """
    if container_name not in MOCK_CONTAINERS:
        return {"error": f"Container '{container_name}' not found. Use list_all_containers first."}
    return {"name": container_name, **MOCK_CONTAINERS[container_name]}


@tool
def get_unhealthy_containers() -> list[dict]:
    """
    Get all containers that are NOT in 'running' status.
    Returns name, status, reason, and resource usage for each unhealthy container.
    Use this to quickly find all problem containers without checking each one individually.
    """
    # LEARNING: Filtering logic lives here in the tool, not in the LLM prompt.
    # Tools should do the heavy lifting — LLMs should reason, not compute.
    unhealthy = [
        {"name": name, **data}
        for name, data in MOCK_CONTAINERS.items()
        if data["status"] != "running"
    ]
    # Sort by severity so the most critical issues appear first
    unhealthy.sort(key=lambda c: SEVERITY_RANK.get(c["status"], 99))
    return unhealthy


@tool
def get_system_summary() -> dict:
    """
    Get a high-level summary of the entire system health.
    Returns total container count, how many are healthy vs unhealthy, and overall status.
    Use this to get a quick overview before diving into individual container details.
    """
    total = len(MOCK_CONTAINERS)
    statuses = [c["status"] for c in MOCK_CONTAINERS.values()]
    healthy_count = statuses.count("running")
    unhealthy_count = total - healthy_count

    # LEARNING: Deterministic logic like this belongs in tools, not LLM prompts.
    # The LLM interprets the result — we compute the result.
    if "stopped" in statuses or "unhealthy" in statuses:
        overall = "CRITICAL"
    elif "degraded" in statuses:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return {
        "overall_status": overall,
        "total_containers": total,
        "healthy": healthy_count,
        "unhealthy": unhealthy_count,
        "status_breakdown": {s: statuses.count(s) for s in set(statuses)},
    }
