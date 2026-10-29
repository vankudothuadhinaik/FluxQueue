# Failure model

## Current implementation

- Enqueue commits before returning the accepted job.
- Requests are schema-validated; serialized job payloads are capped at 64 KiB.
- Tenant-and-queue-scoped idempotency keys return the original job for the same request and reject changed payloads with HTTP 409.
- Bearer API keys map to tenant identities when `API_KEYS` is configured; every job lookup/list/cancel, queue aggregate, and idempotency lookup is tenant-scoped. The legacy `API_KEY` maps to the `default` tenant for single-tenant deployments. Production configuration requires at least one key.
- The worker claims eligible jobs with a lease token, increments attempt count, and renews leases with a heartbeat.
- Success and failure updates require the current lease token, so an old worker cannot overwrite a newer claim.
- Retryable failures use bounded exponential backoff with jitter; exhausted jobs become `dead`.
- Jobs can be scheduled up to 24 hours ahead and are not eligible for claim until due.
- Unknown task types fail as normal job errors; only explicitly registered handlers can run.
- Worker lifecycle logs record claims, outcomes, and stale-lease fencing without emitting job payloads or API keys.
- Active jobs (queued, running, or waiting for retry) are capped per tenant by `MAX_ACTIVE_JOBS_PER_TENANT`; PostgreSQL advisory transaction locks serialize quota checks across API replicas.

The API/worker tests cover key transitions, but the full suite has not yet been confirmed green in GitHub Actions.

## Delivery semantics

Execution is at-least-once, not exactly-once. A handler can perform an external effect and crash before recording success. Handlers with side effects must be idempotent or use downstream idempotency keys.

## Known limits and required release gates

- SQLite does not provide PostgreSQL's row-level `SKIP LOCKED` semantics; use PostgreSQL for concurrent worker deployments.
- PostgreSQL CI integration tests exercise row-lock skipping, concurrent claims, lease reclamation, and stale-token fencing. Process termination and database-restart fault injection remain outstanding.
- Keep migration upgrade/downgrade checks green against fresh and existing schemas (covered by CI migration steps).
- Distributed request rate limiting, key rotation/revocation, production secret handling, and operational controls remain required before public deployment. The serialized payload size cap is implemented and covered by API tests.
- `scripts/benchmark_api.py` provides repeatable enqueue-throughput and API-latency measurements; it does not measure end-to-end completion. Run controlled load/soak tests before making performance claims.
