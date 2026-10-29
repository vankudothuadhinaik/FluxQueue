# Failure model

## Current implementation

- Enqueue commits before returning the accepted job.
- Requests are schema-validated and queue-scoped idempotency keys reject changed payloads with HTTP 409.
- The worker claims eligible jobs with a lease token, increments attempt count, and renews leases with a heartbeat.
- Success and failure updates require the current lease token, so an old worker cannot overwrite a newer claim.
- Retryable failures use bounded exponential backoff with jitter; exhausted jobs become `dead`.
- Unknown task types fail as normal job errors; only explicitly registered handlers can run.

The API/worker tests cover key transitions, but the full suite has not yet been confirmed green in GitHub Actions.

## Delivery semantics

Execution is at-least-once, not exactly-once. A handler can perform an external effect and crash before recording success. Handlers with side effects must be idempotent or use downstream idempotency keys.

## Known limits and required release gates

- SQLite does not provide PostgreSQL's row-level `SKIP LOCKED` semantics; use PostgreSQL for concurrent worker deployments.
- Validate worker recovery with real process termination, database restart, and concurrent workers.
- Test migration upgrade/downgrade against both fresh and existing databases.
- Add authentication, tenant authorization, rate/payload limits, secret handling, and operational controls before public deployment.
- Run reproducible throughput/latency tests before making performance claims.
