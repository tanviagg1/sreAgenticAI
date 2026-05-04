"""
Code tools — @tool functions for the Coding Agent.

LEARNING — Tools for code generation agents:

Unlike health/retrieval/citation agents that READ data,
the Coding Agent also WRITES (generates fixes).

Tools here do two things:
  1. READ: inspect current service configs so the LLM knows what to fix
  2. VALIDATE: check a proposed fix looks reasonable before returning it

LEARNING — Why separate read tools from the fix generation?
The LLM reads service config via tools (grounded in real data),
then generates a fix using its reasoning.
If we just asked "generate a fix for nginx OOM" without reading the config,
the LLM might guess wrong values (hallucinate the current memory limit).
Reading first = grounded fix generation.
"""

import json
from langchain.tools import tool
from mocks.services.nginx_config import (
    NGINX_SERVICE_CONFIG,
    WORKER_SERVICE_CONFIG,
    APP_SERVER_CONFIG,
)

# Registry of all service configs the agent can read
SERVICE_CONFIGS = {
    "nginx": NGINX_SERVICE_CONFIG,
    "worker": WORKER_SERVICE_CONFIG,
    "app-server": APP_SERVER_CONFIG,
}


@tool
def list_fixable_services() -> list[dict]:
    """
    List all services that have configuration available to inspect and fix.
    Call this first to know which services can be analyzed.
    Returns service names and a brief summary of their current config.
    """
    return [
        {
            "service": name,
            "image": config.get("image"),
            "memory_limit": config.get("resources", {}).get("memory_limit"),
            "cpu_limit": config.get("resources", {}).get("cpu_limit"),
        }
        for name, config in SERVICE_CONFIGS.items()
    ]


@tool
def read_service_config(service_name: str) -> dict:
    """
    Read the full configuration for a specific service.
    Use this to understand the current (possibly broken) state before generating a fix.
    service_name must be one of: nginx, worker, app-server.
    Returns the complete service configuration including resources, environment variables, and restart policy.
    """
    # LEARNING: Reading actual config before generating a fix prevents hallucination.
    # The agent knows the REAL current memory_limit, not a guess.
    if service_name not in SERVICE_CONFIGS:
        return {"error": f"Service '{service_name}' not found. Available: {list(SERVICE_CONFIGS.keys())}"}
    return SERVICE_CONFIGS[service_name]


@tool
def validate_fix_schema(fix_json: str) -> dict:
    """
    Validate that a proposed fix JSON string has the required fields and correct types.
    Use this after generating a fix to check it is well-formed before passing to reflection.
    Returns validation result with any missing or invalid fields listed.
    """
    required_fields = ["file", "change_type", "problem_summary", "original", "fixed", "explanation", "risk_level"]
    valid_change_types = ["modify", "add", "delete"]
    valid_risk_levels = ["low", "medium", "high"]

    try:
        fix = json.loads(fix_json)
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"Invalid JSON: {e}"}

    missing = [f for f in required_fields if f not in fix]
    if missing:
        return {"valid": False, "missing_fields": missing}

    errors = []
    if fix.get("change_type") not in valid_change_types:
        errors.append(f"change_type must be one of {valid_change_types}")
    if fix.get("risk_level") not in valid_risk_levels:
        errors.append(f"risk_level must be one of {valid_risk_levels}")
    if not fix.get("fixed") or fix["fixed"] == fix.get("original"):
        errors.append("fixed must be different from original")

    if errors:
        return {"valid": False, "errors": errors}

    return {"valid": True, "fix": fix}


@tool
def get_known_issues(service_name: str) -> list[dict]:
    """
    Get the list of known configuration issues for a service based on its current config.
    Use this to understand what specifically needs fixing before generating a solution.
    Returns a list of issues with their severity and affected config field.
    """
    # LEARNING: Deterministic issue detection lives in a tool (not the LLM).
    # The LLM reasons about what to do — the tool identifies the facts.
    config = SERVICE_CONFIGS.get(service_name)
    if not config:
        return [{"error": f"Service '{service_name}' not found"}]

    issues = []

    if service_name == "nginx":
        mem = config["resources"]["memory_limit"]
        if mem in ("512Mi", "512M"):
            issues.append({
                "severity": "high",
                "field": "resources.memory_limit",
                "current_value": mem,
                "issue": "Memory limit matches current usage — causes OOMKilled on any traffic spike",
                "suggested_fix": "Increase to 1Gi minimum",
            })
        if "NGINX_MEMORY_ALERT_THRESHOLD" not in config.get("environment", {}):
            issues.append({
                "severity": "medium",
                "field": "environment.NGINX_MEMORY_ALERT_THRESHOLD",
                "current_value": None,
                "issue": "No memory alert threshold configured — silent until OOMKilled",
                "suggested_fix": "Add NGINX_MEMORY_ALERT_THRESHOLD=80",
            })

    elif service_name == "worker":
        env = config.get("environment", {})
        if "DB_MAX_CONNECTIONS" not in env:
            issues.append({
                "severity": "high",
                "field": "environment.DB_MAX_CONNECTIONS",
                "current_value": None,
                "issue": "No connection pool limit — worker can exhaust postgres max_connections",
                "suggested_fix": "Add DB_MAX_CONNECTIONS=10",
            })
        if "DB_RETRY_ATTEMPTS" not in env:
            issues.append({
                "severity": "high",
                "field": "environment.DB_RETRY_ATTEMPTS",
                "current_value": None,
                "issue": "No retry logic — crashes immediately on any DB hiccup",
                "suggested_fix": "Add DB_RETRY_ATTEMPTS=3",
            })
        if "DB_CONNECT_TIMEOUT" not in env:
            issues.append({
                "severity": "medium",
                "field": "environment.DB_CONNECT_TIMEOUT",
                "current_value": None,
                "issue": "No connection timeout — hangs indefinitely if DB unreachable",
                "suggested_fix": "Add DB_CONNECT_TIMEOUT=5000",
            })

    elif service_name == "app-server":
        env = config.get("environment", {})
        if config.get("replicas", 1) == 1:
            issues.append({
                "severity": "high",
                "field": "replicas",
                "current_value": 1,
                "issue": "Single replica — no horizontal scaling under high CPU",
                "suggested_fix": "Add autoscaling: min=1, max=3, target_cpu=70%",
            })
        if "REQUEST_TIMEOUT_MS" not in env:
            issues.append({
                "severity": "medium",
                "field": "environment.REQUEST_TIMEOUT_MS",
                "current_value": None,
                "issue": "No request timeout — goroutine pool exhausts under slow requests",
                "suggested_fix": "Add REQUEST_TIMEOUT_MS=5000",
            })

    return issues if issues else [{"severity": "none", "issue": "No known issues found"}]
