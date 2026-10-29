# Operations Runbook

FluxQueue is not production-ready until the deployment-specific checklist in
deployment-readiness.md is completed and the latest CI run passes.

## Tenant keys: rotate or revoke

Keys are configured through API_KEYS, a JSON object mapping bearer secrets to tenant IDs.
Settings are loaded at process startup; changing a secret-manager value alone does not update
already-running API processes.

1. Generate a high-entropy replacement key in the secret manager.
2. Add the replacement key with the same tenant ID while retaining the old key.
3. Roll out/restart every API replica and verify the replacement key against a harmless
   authenticated request.
4. Update the tenant's client configuration to use the replacement key.
5. Remove the old key from API_KEYS, roll out/restart every API replica, and verify that the
   old key receives HTTP 401 while the replacement still works.
6. Never place key values in source control, tickets, logs, screenshots, or benchmark output.

To revoke a key immediately, remove it from API_KEYS and restart/roll out every API replica.
This is operator-managed rotation; there is no self-service key management endpoint.

## Active-job quota

MAX_ACTIVE_JOBS_PER_TENANT defaults to 1000 and counts jobs in queued, running, or retry_wait
states across all queues for one tenant. A submission that exceeds the limit receives HTTP 429.
The check is serialized with a PostgreSQL advisory transaction lock so concurrent API replicas
cannot overshoot the limit for the same tenant. SQLite is for local tests and does not provide
this multi-replica guarantee.

Choose a limit based on worker capacity and database budget. Lowering the limit below a tenant's
current active count does not delete or cancel jobs; it prevents new submissions until the count
falls below the configured value.

## Edge policy and TLS

../deploy/nginx/fluxqueue.conf.example is a starting point for one Nginx proxy. It applies a
128 KiB request-body cap, an IP-based request rate limit, proxy timeouts, and HSTS after TLS is
configured. Replace the example hostname and certificate paths. The IP limit is not tenant-aware
and does not coordinate between multiple independent proxy instances; use a distributed gateway
or shared rate-limit store for a multi-proxy deployment. Keep the application bound to a private
network and do not trust client-supplied forwarded headers unless the trusted proxy overwrites them.

For managed PostgreSQL, set `DATABASE_SSLMODE=verify-full` and provide the CA bundle through
`DATABASE_SSLROOTCERT`. Use `verify-ca` only when hostname verification is intentionally handled
by the managed service's documented certificate policy. Do not use `require`, `prefer`, or an
unverified custom certificate in production. `DATABASE_SSLCERT` and `DATABASE_SSLKEY` are
available for mutual TLS and must be provisioned as protected files, not committed values.

## Health and incident triage

- /health/live indicates the API process is responding.
- /health/ready checks database connectivity; a failure should trigger platform-level readiness
  handling and investigation of PostgreSQL availability, connection limits, and credentials.
- Worker logs include job ID, attempt count, state outcomes, and stale-lease rejection without
  logging job payloads or API keys.
- `/metrics` exposes fixed, low-cardinality counters for enqueued/completed/failed/retried/dead
  jobs, current jobs by state, oldest queued-job age, and aggregate processing duration. Keep it
  on a private monitoring network; no Prometheus server or alert provider is installed by this
  repository.
- Check queue counts and oldest queued-job age before increasing worker replicas. Review dead jobs,
  retry rates, handler duration, lease expiry, and database connection saturation.
- Execution is at-least-once. For external side effects, use downstream idempotency keys and a
  documented recovery/reconciliation procedure.

## Migrations and recovery

- Back up the database before applying a production migration.
- Run migrations against a disposable copy of production-like data first.
- Keep a tested rollback plan; downgrade behavior is not a substitute for a verified backup.
- Perform a restore drill on a separate database and verify both schema and representative job
  records before declaring disaster recovery ready.
- Do not run the PostgreSQL integration tests against a database containing data you need to keep;
  their fixture creates and drops FluxQueue tables.

### Backup and restore procedure

Recommended starting policy (not an established service commitment): daily full backups, point-in-
time recovery where the managed provider supports it, 35-day retention, an RPO target of 24 hours,
and an RTO target agreed with the service owner. Tighten these values only after measuring restore
time and storage cost.

1. Create a fresh disposable PostgreSQL database or provider restore branch; never overwrite the
   source database.
2. Restore the backup using the provider's documented tool, provision the same TLS CA and a
   least-privilege application role, and run `alembic upgrade head`.
3. Verify representative job counts, tenant isolation, idempotency records, and `/health/ready`
   against the restored target.
4. Record backup timestamp, migration revision, restore duration, validation results, and the
   exact target identifier. Destroy the disposable target only after evidence is retained without
   secrets.

Migration rollback is not a disaster-recovery strategy. Prefer forward migrations or restore to a
new target, then switch traffic only after health and data checks pass.

## Benchmarking

Use scripts/benchmark_api.py only against a controlled environment you own. It measures enqueue
API response latency and throughput, not worker completion time. Use a dedicated queue and a
test window, keep the number of submissions below the active-job quota, and clean up test jobs
afterwards. Run a separate end-to-end soak test before making capacity claims.
