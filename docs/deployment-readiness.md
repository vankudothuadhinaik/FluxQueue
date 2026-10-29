# Deployment Readiness Checklist

FluxQueue is an early-stage job queue. Passing CI is necessary, but it does not make a deployment production-ready. Keep the service private until the required gates below are complete.

Local Docker-first staging evidence (2026-10-30): the isolated `fluxqueue-staging` Compose project built successfully, ran API/worker as UID/GID `10001:10001`, passed readiness/authentication/metrics checks, completed a harmless job, produced no test-secret log matches, and recovered a completed job after Compose restart. This is local evidence only; it is not a deployed staging or production validation.

## Before any shared environment

- [ ] Configure `API_KEYS` in the secret manager as a JSON mapping from high-entropy bearer keys to tenant IDs; use legacy `API_KEY` only for a single-tenant deployment.
- [ ] Set `APP_ENV=production`; verify startup fails when both `API_KEY` and `API_KEYS` are absent.
- [ ] Use managed PostgreSQL with TLS, backups, restricted network access, and a least-privilege database role.
- [ ] Replace all local-only database credentials; do not commit `.env` files or secrets.
- [ ] Restrict ingress to the intended private network or trusted reverse proxy. Terminate TLS at a configured proxy/load balancer and enable HSTS there after HTTPS is confirmed.
- [ ] Keep Compose development ports bound to loopback unless intentionally exposing them; review security headers and proxy forwarding settings.
- [ ] Keep the container running as UID/GID `10001:10001`; do not mount writable host paths unless required.
- [ ] Configure CPU/memory limits, restart policy, log retention, and a disk/connection budget.
- [ ] Confirm `/health/live` and `/health/ready` are reachable by the platform health checker, but do not expose administrative or database access publicly.

## Required before public production

- [ ] Verify tenant isolation and `MAX_ACTIVE_JOBS_PER_TENANT` enforcement on the latest successful CI run; implement and test key rotation/revocation.
- [ ] Configure edge rate limiting and request-body limits; review `deploy/nginx/fluxqueue.conf.example` as a single-proxy starting point. Its IP-based limit is not a substitute for distributed tenant-aware limiting in a multi-proxy deployment. The API enforces a PostgreSQL-serialized active-job quota per tenant; verify the configured limit matches capacity.
- [ ] Define and test secret rotation and revocation without logging credentials.
- [ ] Test database outage, worker termination during a handler, lease expiry, retry exhaustion, and recovery after restart.
- [ ] Verify every external side-effecting handler is idempotent; execution is at-least-once, not exactly-once.
- [ ] Export `/metrics` to a private monitoring system and add structured aggregation for database failures and lease-expiry alerts; FluxQueue supplies low-cardinality queue, outcome, age, and processing-duration metrics but does not install an alert provider.
- [ ] Add alert thresholds, an on-call owner, backup restoration procedure, and a rollback procedure.
- [ ] Run `scripts/benchmark_api.py` against a controlled environment, then run a separate end-to-end load/soak test; record throughput, latency percentiles, worker concurrency, and database utilization.
- [ ] Review dependency/security scan results and resolve or explicitly accept findings.
- [ ] Confirm migration rollout and rollback behavior against a disposable copy of production-like data; CI also tests tenant migration against a populated legacy SQLite table.

## Release evidence

Record links to the exact commit, CI run, migration validation, PostgreSQL integration results, security scan, load-test report, and deployment configuration review. A workflow definition is not evidence that a workflow passed; mark a gate complete only after its result has been inspected.

## Current limitations

- API keys map to tenant IDs when `API_KEYS` is configured; this mapping takes precedence over the legacy `API_KEY`. The legacy key maps to `default` and is for single-tenant use only. Individual user identities and self-service key rotation are not implemented.
- Job execution is at-least-once. A worker can perform an external side effect and crash before acknowledging success.
- The repository's CI smoke test checks container startup, health endpoints, and protected-route authentication. It does not validate a real reverse proxy, TLS termination, production secret manager, backup restoration, or production traffic.
