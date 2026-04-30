# Runbook: High CPU Usage

**ID:** RB-002
**Severity:** P2
**Applies to:** app-server, worker, api-gateway
**Last updated:** 2026-02-10

---

## Overview

Sustained high CPU (>85% for more than 5 minutes) indicates a service under stress.
It may cause request timeouts, SLO breaches, and eventually service degradation or crash.

---

## Symptoms

- CPU usage above 85% sustained for 5+ minutes
- Request latency increasing (p99 > 2x baseline)
- Log lines: `cpu usage: 95% — critical`
- Log lines: `goroutine pool exhausted` or `worker pool exhausted`
- Log lines: `request timeout exceeded`
- Error rate climbing above 1%

---

## Diagnosis Steps

### Step 1: Confirm CPU spike is real and sustained
```bash
docker stats <container> --no-stream
```
A brief spike (< 2 min) is usually a burst — monitor and wait.
Sustained (> 5 min) requires action.

### Step 2: Identify the cause
**Traffic surge:**
- Check request rate in logs — are requests per second higher than normal?
- Compare to baseline traffic for this time of day

**Runaway process:**
- Check if one specific endpoint is consuming all CPU
- Look for log patterns: same endpoint timing out repeatedly

**Inefficient query or job:**
- Check for slow database queries (look in postgres logs)
- Check if a scheduled job started recently

### Step 3: Check downstream impact
- Is error rate above SLO threshold (1%)?
- Is p99 latency above SLO threshold (2000ms)?
- Are requests being dropped or queued?

---

## Remediation

### Immediate
1. If traffic surge: enable rate limiting at the load balancer
   ```nginx
   limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
   ```
2. If runaway process: identify and kill the specific request/job
3. Scale horizontally if possible:
   ```bash
   kubectl scale deployment app-server --replicas=3
   ```

### Short-term
1. Add CPU-based autoscaling (scale out at 70% CPU)
2. Add request timeout at 5 seconds to prevent goroutine pool exhaustion
3. Profile the hottest code paths with pprof or py-spy

### Long-term
1. Optimize the identified slow endpoints
2. Add caching for expensive computations
3. Implement circuit breakers for downstream service calls

---

## SLO Breach Protocol

If error rate > 1% OR p99 latency > 2000ms:
1. Declare incident immediately — do not wait for auto-recovery
2. Page secondary on-call if primary cannot resolve within 15 minutes
3. Consider rollback to previous version if recent deployment is suspected cause

---

## Related Runbooks

- RB-005: SLO Breach Response
- RB-004: Container Restart Loop
