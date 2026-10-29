# Failure model

## Verified by design in current foundation

- The enqueue service commits before returning the accepted job.
- Request structure is validated.
- Repeating a queue-scoped idempotency key with the same canonical request returns the original record.
- Reusing that key with changed request data returns HTTP 409.
- Queued/retry-wait jobs can be cancelled; other states return HTTP 409.

These describe intended code behavior; run the local test suite and CI to verify it in a particular commit.

## Not implemented yet

No worker execution, retry loop, dead-letter flow, delayed scheduling, lease recovery, stale-worker fencing, auth, or benchmark results are delivered by this foundation.

## Delivery semantics

A future worker implementation should target at-least-once execution. Exactly-once external side effects cannot be guaranteed by the queue alone: a handler can complete a side effect and crash before persisting its acknowledgement. Handlers should be idempotent or use downstream idempotency keys.

## Required fault-injection cases

1. Worker exits after claim but before execution.
2. Worker exits during a handler.
3. Handler finishes but acknowledgement is lost.
4. Lease expires and another worker claims the job.
5. Stale worker attempts acknowledgement after re-claim.
6. Database disconnect during enqueue or acknowledgement.
7. Restart while delayed/retry jobs are due.
8. Concurrent requests reuse a single idempotency key.
