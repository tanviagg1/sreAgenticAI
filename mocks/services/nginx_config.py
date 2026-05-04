"""
Mock nginx service configuration — intentionally broken for the Coding Agent to fix.

This represents a docker-compose style service config stored as Python dicts.
In a real system, the Coding Agent would read actual docker-compose.yml, Kubernetes
manifests, or application source files.

LEARNING — Why mock code instead of real files?
We want the Coding Agent to practice:
  - Reading a service config
  - Identifying what is wrong
  - Generating a specific code/config fix
  - Critiquing that fix before applying it

Using Python dicts as "config" keeps the focus on the AI concepts
without requiring actual Docker or k8s setup.
"""

# Current (broken) nginx configuration
# Problem: memory limit is 512Mi — exactly what nginx is using when it OOMKills
NGINX_SERVICE_CONFIG = {
    "service_name": "nginx",
    "image": "nginx:1.25",
    "port": 80,
    "resources": {
        "cpu_limit": "500m",       # 0.5 CPU core
        "cpu_request": "100m",
        "memory_limit": "512Mi",   # BUG: too low — nginx hits this and OOMKills
        "memory_request": "256Mi",
    },
    "restart_policy": "on-failure:5",
    "health_check": {
        "path": "/health",
        "interval": "30s",
        "timeout": "10s",
        "retries": 3,
    },
    "environment": {
        "NGINX_WORKER_PROCESSES": "auto",
        "NGINX_WORKER_CONNECTIONS": "1024",
        # BUG: no memory alerting threshold set
    }
}

# Current (broken) worker configuration
# Problem: no retry logic, no connection pool limit — causes crash on DB unavailability
WORKER_SERVICE_CONFIG = {
    "service_name": "worker",
    "image": "worker:2.1.4",
    "resources": {
        "cpu_limit": "1000m",
        "memory_limit": "512Mi",
        "memory_request": "256Mi",
    },
    "restart_policy": "on-failure:5",
    "environment": {
        "DATABASE_URL": "postgres://postgres:5432/app",
        "QUEUE_NAME": "jobs",
        # BUG: DB_MAX_CONNECTIONS not set — uses default unlimited connections
        # BUG: DB_RETRY_ATTEMPTS not set — crashes on first DB failure
        # BUG: DB_CONNECT_TIMEOUT not set — hangs indefinitely on connection failure
    },
    "depends_on": ["postgres", "redis"],  # BUG: no health condition — starts before DB is ready
}

# Current (broken) app-server configuration
# Problem: no CPU-based scaling, no request timeout
APP_SERVER_CONFIG = {
    "service_name": "app-server",
    "image": "app-server:3.4.1",
    "port": 8080,
    "replicas": 1,              # BUG: single replica — no horizontal scaling
    "resources": {
        "cpu_limit": "2000m",
        "memory_limit": "1Gi",
    },
    "environment": {
        "WORKER_POOL_SIZE": "200",
        "DATABASE_URL": "postgres://postgres:5432/app",
        # BUG: REQUEST_TIMEOUT_MS not set — requests can hang indefinitely
        # BUG: no autoscaling configured
    },
}
