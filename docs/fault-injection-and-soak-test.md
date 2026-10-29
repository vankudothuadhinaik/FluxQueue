# Controlled Fault-Injection and Soak-Test Runbook

This runbook is an execution plan, not evidence that a test has passed. Run it only in an isolated,
disposable environment you own. Never inject faults into production or point the PostgreSQL
integration tests at data that must be preserved.

## 1. Record the test envelope

Before starting, record:

- Git commit SHA and container image digest.
- Python, PostgreSQL, Docker/Compose, and operating-system versions.
- API and worker replica counts, worker lease duration, retry settings, and tenant quota.
- Database CPU, memory, connection limit, storage, and network topology.
- Test payload shape, enqueue rate, concurrency, duration, and cleanup plan.
- Exact commands, timestamps, logs, result counts, latency percentiles, and any deviations.

Use a fresh database and non-production credentials. Verify backups are not your only recovery copy.

## 2. Establish a baseline

1. Start the stack using the repository's documented local Compose procedure.
2. Confirm `/health/live` and `/health/ready` respond successfully.
3. Confirm an unauthenticated API request receives HTTP 401 and an authenticated request succeeds.
4. Submit a small batch of `echo` jobs and verify every accepted job reaches a terminal state.
5. Record API latency, completion latency, queue depth, oldest-job age, retry/dead counts, worker
   restarts, database connections, and resource utilization.
6. Save the baseline results and commit SHA with the release evidence.

## 3. Worker termination and lease recovery

Run only with a disposable database and a deliberately long-running test handler or workload.

1. Submit one job and verify it reaches `running` with a lease.
2. Terminate the worker process without graceful shutdown while that handler is executing.
3. Verify the job is not acknowledged as succeeded merely because the process disappeared.
4. Wait for the lease to expire, restart a worker, and verify the job is reclaimed or dead-lettered
   according to its configured attempt limit.
5. Verify a stale worker/token cannot acknowledge or fail the reclaimed job.
6. Repeat with the final permitted attempt and verify an expired final attempt becomes `dead`
   instead of being reclaimed forever.

Expected: no stale-token state mutation; abandoned work becomes eligible after lease expiry; retry
exhaustion is finite. Since execution is at-least-once, the test must also document whether the
handler could have performed a side effect before termination.

## 4. Database outage and recovery

Use an isolated test deployment where database connectivity can be intentionally interrupted.

1. Establish a healthy baseline with workers polling and the API accepting a small number of jobs.
2. Block or pause the test deployment's database connection path using its own orchestration or
   network controls. Do not change shared infrastructure.
3. Observe API readiness and errors, worker process health, retry behavior, and logs. Confirm logs
   contain no API keys or job payloads.
4. Restore connectivity and wait for the configured recovery window.
5. Verify workers resume polling, queued jobs are processed, and no job is incorrectly marked
   succeeded solely because connectivity returned.
6. Compare accepted submissions against persisted jobs and record any ambiguous client outcomes.
   Clients should use idempotency keys when retrying submissions after an uncertain response.

Expected: processes remain recoverable; readiness reflects database failure; the queue resumes
after connectivity returns; no unexplained loss or duplicate terminal acknowledgements. If these
expectations fail, capture logs and database state before cleanup.

## 5. Retry, poison job, and tenant isolation

1. Submit a test-only handler that deterministically fails. Confirm retry delay prevents immediate
   reclaim, attempt count increases, and the job eventually reaches `dead` at the attempt limit.
2. Submit a valid job for another tenant and verify one tenant cannot read, cancel, or list the
   other's jobs.
3. Fill a tenant to the configured active-job quota in the disposable environment and verify the
   next submission receives HTTP 429; verify submissions resume after active jobs reach terminal
   states.
4. Run concurrent submissions from multiple API replicas if that topology is part of the intended
   deployment. Record whether the quota is maintained under concurrency.

Never add a test-only failure handler to a publicly reachable deployment.

## 6. Load and soak test

Use `scripts/benchmark_api.py --help` first to inspect the benchmark's actual arguments; do not
assume it measures worker completion throughput. Run it only against the isolated target and within
the active-job quota. Then perform a separate end-to-end workload that measures enqueue-to-terminal
completion time.

Run at least these phases, scaling down if the environment is small:

- Warm-up: 5 minutes at a low, steady enqueue rate.
- Load steps: 10 minutes each at increasing rates; stop increasing when latency, errors, queue age,
  or resource use exceeds the predeclared safety threshold.
- Soak: at a sustainable rate for at least 60 minutes.
- Recovery: stop submissions and measure time until backlog returns to baseline.

Report request rate, accepted/rejected/error counts, p50/p95/p99 enqueue latency, p50/p95/p99
completion latency, jobs per second completed, maximum queue depth, oldest-job age, retries, dead
jobs, worker concurrency, CPU/memory, database connections, and recovery time. Include workload
shape, environment size, and commit SHA with every number.

Predeclare pass/fail thresholds based on the intended service objective and test environment. Do
not publish a throughput number without the workload, environment, and completion-vs-enqueue
measurement distinction.

## 7. Closeout and cleanup

- Stop load generation before cleaning up jobs.
- Preserve logs, test reports, relevant metrics, configuration (with secrets removed), and exact
  commit/image identifiers.
- Confirm no test workload remains and the isolated environment is shut down.
- Record each scenario as PASS, FAIL, or NOT RUN, with evidence links and an owner for every failure.
- Update `docs/deployment-readiness.md` only after the evidence has been reviewed. A written
  procedure, CI workflow definition, or a successful baseline does not prove fault injection,
  soak testing, production TLS, backup restoration, or secret-manager integration passed.
