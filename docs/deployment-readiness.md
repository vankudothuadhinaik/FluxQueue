# Deployment Readiness Checklist

FluxQueue is an early-stage job queue. Passing CI is necessary, but it does not make a deployment production-ready. Keep the service private until the required gates below are complete.

## Before any shared environment

- [ ] Configure `API_KEYS` in the secret manager as a JSON mapping from high-entropy bearer keys to tenant IDs; use legacy `API_KEY` only for a single-tenant deployment.
- [ ] Set `APP_ENV=production`; verify startup fails when both `API_KEY` and `API_KEYS` are absent.
- [ ] Use managed PostgreSQL with TLS, backups, restricted network access, and a least-privilege database role.
- [ ] Replace all local-only database credentials; do not commit `.env` files or secrets.
- [ ] Restrict ingress to the intended private network or trusted reverse proxy. Terminate TLS at a configured proxy/load balancer.
- [ ] Keep the container running as UID/GID `10001:10001`; do not mount writable host paths unless required.
- [ ] Configure CPU/memory limits, restart policy, log retention, and a disk/connection budget.
- [ ] Confirm `/health/live` and `/health/ready` are reachable by the platform health checker, but do not expose administrative or database access publicly.

## Required before public production

- [ ] Verify tenant isolation across listing, reads, cancellation, queue counts, and idempotency on the latest successful CI run; implement key rotation/revocation and per-tenant quotas.
- [ ] Add rate limiting and request-body limits at the edge, plus per-tenant queue and job quotas.
- [ ] Define and test secret rotation and revocation without logging credentials.
- [ ] Test database outage, worker termination during a handler, lease expiry, retry exhaustion, and recovery after restart.
- [ ] Verify every external side-effecting handler is idempotent; execution is at-least-once, not exactly-once.
- [ ] Add structured logs and operational metrics for queue depth, oldest-job age, retries, dead jobs, lease expiry, handler duration, and database failures.
- [ ] Define alert thresholds, an on-call owner, backup restoration procedure, and a rollback procedure.
- [ ] Run reproducible load/soak tests and record throughput, latency percentiles, worker concurrency, and database utilization.
- [ ] Review dependency/security scan results and resolve or explicitly accept findings.
- [ ] Confirm migration rollout and rollback behavior against a disposable copy of production-like data.

## Release evidence

Record links to the exact commit, CI run, migration validation, PostgreSQL integration results, security scan, load-test report, and deployment configuration review. A workflow definition is not evidence that a workflow passed; mark a gate complete only after its result has been inspected.

## Current limitations

- API keys map to tenant IDs when `API_KEYS` is configured; this mapping takes precedence over the legacy `API_KEY`. The legacy key maps to `default` and is for single-tenant use only. Individual user identities and self-service key rotation are not implemented.
- Job execution is at-least-once. A worker can perform an external side effect and crash before acknowledging success.
- The repository's CI smoke test checks container startup, health endpoints, and protected-route authentication. It does not validate a real reverse proxy, TLS termination, production secret manager, backup restoration, or production traffic.
