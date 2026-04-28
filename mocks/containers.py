"""
Mock container registry — simulates a real Docker/Kubernetes environment.

LEARNING: In a real SRE system, this data would come from:
  - Docker SDK: docker.from_env().containers.list()
  - Kubernetes: kubectl get pods -o json
  - Prometheus metrics API

We mock it here so the agent logic is testable without real infrastructure.
The structure mirrors what you'd get from a real container health check.
"""

# Each container has:
#   status:           running | unhealthy | degraded | stopped
#   reason:           why it's not healthy (None if running fine)
#   cpu_percent:      current CPU usage (0-100)
#   memory_mb:        current memory usage in MB
#   memory_limit_mb:  hard memory cap — hitting this causes OOMKilled
#   restarts:         how many times it crashed and restarted
#   uptime_seconds:   how long it has been running

MOCK_CONTAINERS = {
    "nginx": {
        "status": "unhealthy",
        "reason": "OOMKilled",          # Linux kernel killed it — ran out of memory
        "cpu_percent": 45,
        "memory_mb": 512,
        "memory_limit_mb": 512,         # At 100% of limit — this is why it OOMKilled
        "restarts": 3,
        "uptime_seconds": 120,
    },
    "postgres": {
        "status": "running",
        "reason": None,
        "cpu_percent": 12,
        "memory_mb": 256,
        "memory_limit_mb": 1024,
        "restarts": 0,
        "uptime_seconds": 86400,        # Running for 1 day — healthy
    },
    "redis": {
        "status": "running",
        "reason": None,
        "cpu_percent": 5,
        "memory_mb": 64,
        "memory_limit_mb": 256,
        "restarts": 0,
        "uptime_seconds": 86400,
    },
    "app-server": {
        "status": "degraded",
        "reason": "high_cpu",           # Not crashed, but performance is impacted
        "cpu_percent": 95,              # Dangerously high CPU
        "memory_mb": 800,
        "memory_limit_mb": 1024,
        "restarts": 1,
        "uptime_seconds": 3600,
    },
    "worker": {
        "status": "stopped",
        "reason": "exit_code_1",        # Non-zero exit = crashed with error
        "cpu_percent": 0,
        "memory_mb": 0,
        "memory_limit_mb": 512,
        "restarts": 5,                  # Crashed 5 times — likely a serious bug
        "uptime_seconds": 0,
    },
}

# Severity ranking used by the health agent to prioritize issues
# LEARNING: Defining this as data (not inside the LLM prompt) keeps logic deterministic
SEVERITY_RANK = {
    "stopped": 1,       # Highest priority — service is completely down
    "unhealthy": 2,
    "degraded": 3,
    "running": 4,       # Lowest — no action needed
}
