# Runbook: SLO Breach Response

**ID:** RB-005
**Severity:** P1
**Applies to:** All customer-facing services
**Last updated:** 2026-02-28

---

## Overview

An SLO (Service Level Objective) breach means we are failing our reliability commitments.
Immediate action is required — every minute of breach erodes error budget and impacts users.

---

## Our SLOs

| Metric | Target | Breach threshold |
|---|---|---|
| Availability | 99.9% | < 99.9% over 30 days |
| p99 latency | < 2000ms | > 2000ms sustained 5 min |
| Error rate | < 1% | > 1% sustained 5 min |

---

## Symptoms

- Log line: `p99 latency: 8200ms — SLO breach (threshold: 2000ms)`
- Log line: `error rate: 12% — SLO breach (threshold: 1%)`
- Monitoring dashboard showing red SLO indicators
- User-facing error pages or slow load times

---

## Immediate Response (first 5 minutes)

### Step 1: Declare the incident
- Post in #incidents Slack channel: "SLO breach on [service], investigating"
- Start incident timer
- Assign incident commander (IC)

### Step 2: Assess blast radius
- Which services are affected?
- Is this a full outage or degraded performance?
- Are all users affected or a subset (region, user tier)?

### Step 3: Check for obvious causes (in order)
1. Recent deployment? → Consider rollback immediately
2. Traffic spike? → Enable rate limiting
3. Downstream dependency down? → Check postgres, redis, external APIs
4. Resource exhaustion? → Check CPU (RB-002) and memory (RB-001)

---

## Rollback Procedure

If a recent deployment is suspected:
```bash
# Docker
docker-compose up -d --scale app-server=0
docker-compose up -d <previous-image>

# Kubernetes
kubectl rollout undo deployment/app-server
kubectl rollout status deployment/app-server
```

---

## Communication Template

**Initial (< 5 min):**
> We are investigating elevated error rates on [service]. Impact: [description]. ETA for update: 15 min.

**Update (every 15 min):**
> Update on [service] incident: [current status]. We have identified [cause] and are [action].

**Resolution:**
> [Service] is restored. Root cause: [cause]. Fix applied: [fix]. Post-mortem scheduled for [date].

---

## Error Budget Calculation

Monthly error budget = total minutes × (1 - SLO target)
Example: 99.9% SLO = 43.8 minutes of downtime per month

After a breach, calculate budget consumed:
```
budget_consumed = breach_duration_minutes / total_budget_minutes × 100%
```

If budget is < 10% remaining: freeze all non-critical deployments until month reset.

---

## Post-Incident Requirements

Within 48 hours:
- [ ] Post-mortem document written
- [ ] Root cause identified and documented
- [ ] Action items created with owners and due dates
- [ ] Error budget impact calculated

---

## Related Runbooks

- RB-001: OOMKilled
- RB-002: High CPU Usage
- RB-003: Database Connection Failures
