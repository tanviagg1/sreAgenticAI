# Runbook: Container Restart Loop

**ID:** RB-004
**Severity:** P1-P2 depending on service
**Applies to:** All containerized services
**Last updated:** 2026-01-20

---

## Overview

A container restart loop (CrashLoopBackOff in Kubernetes, repeated restarts in Docker)
means a container keeps failing shortly after starting. Left unresolved, it causes
sustained service unavailability.

---

## Symptoms

- Container restart count > 3 in a short period
- Container status cycling between running and stopped/error
- Log pattern: service starts, fails, restarts repeatedly
- Exit codes: 1 (application error), 137 (OOMKilled), 143 (SIGTERM timeout)

---

## Exit Code Reference

| Exit Code | Meaning | Likely cause |
|---|---|---|
| 0 | Clean exit | Intentional stop |
| 1 | Application error | Bug, missing config, failed health check |
| 137 | SIGKILL (OOMKilled) | Memory limit exceeded |
| 139 | Segfault | Corrupted memory, native lib bug |
| 143 | SIGTERM timeout | Graceful shutdown exceeded timeout |

---

## Diagnosis Steps

### Step 1: Get the exit code
```bash
docker inspect <container> --format='{{.State.ExitCode}}'
```

### Step 2: Read the last logs before crash
```bash
docker logs <container> --tail=50
```
Look for the final error message before the crash — this is the root cause.

### Step 3: Check if it fails immediately or after some time
- Fails immediately on start: likely missing config, bad env var, or dependency unavailable
- Fails after 30-60 seconds: health check failing, or dependency becomes unavailable

### Step 4: Check dependencies
Does the service depend on postgres, redis, or another service?
Try to connect to the dependency manually to verify it is available.

---

## Remediation by Exit Code

### Exit code 1 (application error)
1. Read the full logs — the error message is the answer
2. Common causes:
   - Missing environment variable → add it to docker-compose or k8s secret
   - Dependency not ready → add startup retry logic
   - Bug in recent deployment → rollback

### Exit code 137 (OOMKilled)
Follow RB-001: OOMKilled runbook.

### Exit code 143 (SIGTERM timeout)
1. The service is not shutting down gracefully
2. Increase the stop grace period:
   ```yaml
   stop_grace_period: 30s
   ```
3. Ensure the service handles SIGTERM and finishes in-flight requests

---

## Preventing Restart Loops

1. Always implement health checks — distinguish between starting and ready states
2. Use `depends_on` with health conditions so services wait for dependencies:
   ```yaml
   depends_on:
     postgres:
       condition: service_healthy
   ```
3. Implement startup retry logic with exponential backoff
4. Set restart policies appropriately: `on-failure:5` not `always`

---

## Related Runbooks

- RB-001: OOMKilled
- RB-003: Database Connection Failures
