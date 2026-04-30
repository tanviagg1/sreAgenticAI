# Runbook: OOMKilled — Out of Memory Container

**ID:** RB-001
**Severity:** P1
**Applies to:** All containerized services
**Last updated:** 2026-01-15

---

## Overview

OOMKilled means the Linux kernel's OOM (Out of Memory) Killer terminated the container process
because it exceeded its configured memory limit. This is one of the most common container failures.

---

## Symptoms

- Container status shows `OOMKilled` or `unhealthy`
- Log line: `kill process (nginx) score 950 or sacrifice child`
- Log line: `worker process killed by kernel OOM killer`
- Container restarts repeatedly (restart count > 2 indicates chronic issue)
- Memory usage consistently at 90%+ of the configured limit

---

## Diagnosis Steps

### Step 1: Confirm OOM is the cause
```bash
kubectl describe pod <pod-name> | grep -A5 "Last State"
# Look for: Reason: OOMKilled
```

### Step 2: Check memory trend before the kill
Review logs for memory usage warnings in the 30 minutes before the OOMKilled event.
A steady climb (82% -> 94% -> 99% -> OOMKilled) indicates a memory leak.
A sudden spike indicates a traffic surge or runaway request.

### Step 3: Check restart count
- 1-2 restarts: likely a one-off spike, increase limit temporarily
- 3+ restarts: memory leak — must fix the root cause, not just raise the limit

---

## Remediation

### Immediate (stop the bleeding)
1. Increase the container memory limit by 2x as a temporary measure:
   ```yaml
   resources:
     limits:
       memory: "1Gi"   # was 512Mi
   ```
2. Restart the container to clear current memory state
3. Alert the on-call engineer if restart count > 3

### Short-term (within 24 hours)
1. Profile memory usage with: `docker stats <container>`
2. Check for memory leaks in application code (unclosed connections, growing caches)
3. Add memory usage alerting at 80% threshold

### Long-term (within 1 week)
1. Implement proper memory limits based on profiled usage + 30% headroom
2. Add horizontal scaling so traffic surges distribute load
3. Add /metrics endpoint to expose memory usage to Prometheus

---

## Post-Incident

- File incident report with: service name, restart count, memory limit at time of incident
- Add memory limit increase to infrastructure PR
- Schedule memory profiling session for the affected service

---

## Related Runbooks

- RB-004: Container Restart Loop
- RB-005: SLO Breach Response
