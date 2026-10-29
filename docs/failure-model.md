# Failure model

## Current guarantees

- An accepted job is committed before the API returns.
- Pydantic validates the request structure.
- Repeated queue-scoped idempotency keys with the same request return the existing job.
- Reusing a key with different input returns HTTP 409.
- Cancellation currently applies only to queued/retry-wait jobs.

## Not yet guaranteed

The foundation does not yet execute jobs, retry handlers, recover crashed workers, fence stale acknowledgements, or promise exactly-once external side effects. No performance benchmark is claimed.

## Target delivery semantics

A worker queue commonly provides at-least-once execution. A handler may complete an external effect and crash before acknowledgement; side-effecting handlers must be idempotent.

## Required recovery tests

1. Worker exits after claim but before execution.
2. Worker exits mid-handler.
3. Handler succeeds but acknowledgement is lost.
4. Lease expires and another worker reclaims the job.
5. Old worker tries to acknowledge after re-claim.
6. Database disconnects during enqueue/acknowledgement.
7. Restart while scheduled/retry work is due.
8. Concurrent submissions reuse one idempotency key.
