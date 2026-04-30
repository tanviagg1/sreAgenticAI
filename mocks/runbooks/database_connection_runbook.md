# Runbook: Database Connection Failures

**ID:** RB-003
**Severity:** P1
**Applies to:** worker, app-server, any service connecting to postgres
**Last updated:** 2026-03-01

---

## Overview

Database connection failures cause downstream services to fail, crash, or enter a retry loop.
They are typically caused by: connection pool exhaustion, database restart, network partition,
or misconfigured credentials.

---

## Symptoms

- Log line: `database connection lost: connection refused`
- Log line: `FATAL: too many connections`
- Log line: `connection refused to postgres:5432`
- Service entering crash loop due to failed DB connection on startup
- Worker container showing exit_code=1 repeatedly

---

## Diagnosis Steps

### Step 1: Is postgres running?
```bash
docker ps | grep postgres
kubectl get pod -l app=postgres
```
If postgres is down — that is the root cause. See postgres restart procedure.

### Step 2: Check connection count
```sql
SELECT count(*) FROM pg_stat_activity;
SELECT max_conn, used FROM
  (SELECT count(*) used FROM pg_stat_activity) t1,
  (SELECT setting::int max_conn FROM pg_settings WHERE name='max_connections') t2;
```
If used == max_conn: connection pool is exhausted. This is the most common cause.

### Step 3: Check which clients are holding connections
```sql
SELECT client_addr, state, count(*)
FROM pg_stat_activity
GROUP BY client_addr, state
ORDER BY count DESC;
```
Look for a single client holding many idle connections — indicates a connection leak.

### Step 4: Check postgres logs for the timeline
Look for: `connection refused: max_connections limit reached`
Compare timestamp to when the worker started crashing.

---

## Remediation

### Immediate: Connection pool exhaustion
1. Kill idle connections to free up capacity:
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle'
   AND query_start < now() - interval '5 minutes';
   ```
2. Restart the offending service to reset its connection pool
3. Temporarily increase max_connections if needed:
   ```sql
   ALTER SYSTEM SET max_connections = 200;
   SELECT pg_reload_conf();
   ```

### Immediate: Postgres is down
1. Check postgres container logs for the crash reason
2. Restart postgres: `docker restart postgres` or `kubectl rollout restart deployment/postgres`
3. Verify all clients reconnect successfully after restart

### Short-term
1. Implement connection pooling with PgBouncer (reduces connections per service)
2. Set connection pool size limits in each service's database config
3. Add connection count alerting at 80% of max_connections

### Long-term
1. Move to PgBouncer in transaction mode for high-throughput services
2. Implement retry logic with exponential backoff in all services
3. Add health check that verifies DB connectivity before service starts

---

## Recovery Verification

After remediation, verify:
- [ ] `SELECT count(*) FROM pg_stat_activity` is well below max_connections
- [ ] Worker service has restarted and is processing jobs
- [ ] No new connection refused errors in worker logs for 5 minutes

---

## Related Runbooks

- RB-001: OOMKilled
- RB-004: Container Restart Loop
