# Architecture

## Current implementation

FluxQueue is a FastAPI API plus a separate polling worker. SQLAlchemy persists jobs in PostgreSQL (the Docker Compose default). SQLite remains useful for isolated local tests.

```mermaid
flowchart LR
  Client[Client] --> API[FastAPI API]
  API --> DB[(PostgreSQL)]
  Worker[Worker process] --> DB
  Worker --> Registry[Registered handler registry]
  API --> Ops[Health and OpenAPI]
```

The API supports enqueue with a 64 KiB serialized-payload limit, retrieval, filtering, pagination, queue counts, cancellation of queued/retry-wait jobs, liveness, and readiness. Bearer API keys resolve to a tenant identity. The legacy `API_KEY` maps to the `default` tenant; multi-tenant deployments use `API_KEYS`, a JSON mapping from secrets to tenant IDs. The worker currently registers `echo`, `add_numbers`, and `uppercase`; unknown task names fail through the retry/dead-letter lifecycle rather than being dynamically imported or executed.

## Claim and lease protocol

The worker selects the highest-priority eligible job and locks the selected row with `FOR UPDATE SKIP LOCKED` on databases that support it. It changes the state to `running`, increments the attempt count, and assigns a random lease token and expiry in a short transaction. The handler runs outside that transaction.

A heartbeat renews the lease only while the same token owns a running job. Success and failure updates also require the current token, fencing out stale workers after a lease is reclaimed. Expired running leases can be reclaimed; a crashed job that has already consumed all attempts becomes `dead`.

## Retry behavior

Failures are stored as bounded error text. Jobs below their attempt limit transition to `retry_wait` with bounded exponential backoff and jitter. Exhausted jobs transition to `dead`. New jobs can be delayed by up to 24 hours; workers claim them only once `run_at` is due. Side-effecting handlers must remain idempotent because a worker can complete an external side effect and crash before persisting success.

## Migrations and deployment

Alembic applies the initial worker lease migration and the tenant-isolation migration (`0002_tenant_isolation`). The migration can add lease/scheduling fields to an existing `jobs` table and creates the full current schema for a fresh database. Docker Compose starts PostgreSQL, runs migrations before API startup, and starts the worker after API readiness.

Job retrieval, listing, cancellation, queue aggregates, and idempotency lookups are filtered by the authenticated tenant. Migration `0002_tenant_isolation` backfills existing jobs to `default` and scopes the uniqueness constraint by tenant, queue, and idempotency key. Production settings fail closed unless `API_KEY` or `API_KEYS` is configured. Per-user identities, rate limiting, per-tenant quotas, key rotation/revocation, process-kill/database-outage fault injection, and full public deployment hardening are still missing. CI includes PostgreSQL integration checks for `SKIP LOCKED`, concurrent claims, lease reclamation, and stale-token fencing; these checks must pass on the latest run before release. The current API must not be exposed publicly until those are addressed.
