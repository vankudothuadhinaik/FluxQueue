# FluxQueue

[![CI](https://github.com/vankudothuadhinaik/FluxQueue/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vankudothuadhinaik/FluxQueue/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A durable job-processing platform built with FastAPI, SQLAlchemy, and PostgreSQL.

> **Status: active foundation.** Tenant-scoped API authorization and a PostgreSQL-serialized active-job quota per tenant are implemented with regression tests. Production hardening still requires verified CI, edge rate limiting, fault-injection testing, benchmarks, and deployment review.

## Current capabilities

- Validated job submission with a 64 KiB serialized-payload cap and commit-before-acceptance.
- Tenant-scoped API keys and tenant-isolated job reads, listings, cancellation, queue counts, and idempotency keys. When `API_KEYS` is non-empty, it takes precedence over the legacy single-tenant `API_KEY`.
- Job retrieval, filtering, pagination, queue counts, and cancellation.
- Separate worker process with registered handlers: `echo`, `add_numbers`, and `uppercase`.
- Lease expiry/reclaim, heartbeat renewal, stale-token fencing, bounded exponential retry, terminal `dead` state, and payload-free worker lifecycle logs.
- Non-root API/worker container, baseline security response headers, loopback-bound local Compose ports, Alembic migrations, SQLite unit/API tests, PostgreSQL concurrency integration tests, container startup/auth smoke checks, Ruff, CodeQL, automated dependency auditing, Dependabot, and optional Codecov.

## Quick start

Requirements: Python 3.12+, Docker, Docker Compose.

```bash
docker compose up --build
```

Open http://localhost:8000/docs. Submit a job:

```bash
curl -X POST http://localhost:8000/api/v1/jobs -H 'content-type: application/json' -H 'Idempotency-Key: demo-001' -d '{"task_type":"echo","payload":{"message":"hello FluxQueue"},"queue":"default","priority":5,"max_attempts":3}'
```

The worker polls the same PostgreSQL database and executes registered task types. Set `delay_seconds` from 0 to 86400 in a job request to schedule it for later; the worker will not claim it before its scheduled time. For arithmetic, use `task_type: "add_numbers"` with `payload: {"numbers":[1,2,3]}`; for text conversion, use `task_type: "uppercase"` with `payload: {"text":"fluxqueue"}`.

The Compose database password is a local-development default. Set `POSTGRES_PASSWORD` before shared use. For local development, `API_KEY` is optional. For production, set `APP_ENV=production` and configure `API_KEYS` as a JSON object mapping each high-entropy bearer key to a tenant identifier, for example `{"replace-with-a-long-random-secret":"tenant-a"}`. Send the key as `Authorization: Bearer <key>`. The legacy `API_KEY` setting is retained for single-tenant deployments and maps to the `default` tenant; it does not provide tenant isolation by itself. When `API_KEYS` is non-empty, it takes precedence and the legacy key is not accepted. Store keys in Doppler or another secret manager, never in committed files.

## API

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/queues`
- `GET /health/live` and `GET /health/ready`

## Python SDK and CLI

Install FluxQueue in the environment where you want to call the API:

```bash
python -m pip install -e .
```

The dependency-free synchronous Python client supports submit, get, list, cancel, and queue counts:

```python
from fluxqueue.sdk import FluxQueueClient

client = FluxQueueClient("http://127.0.0.1:8000", api_key="your-tenant-key")
job = client.submit(
    {"task_type": "echo", "payload": {"message": "hello"}},
    idempotency_key="example-001",
)
print(client.get_job(job["id"]))
print(client.list_jobs(status="queued", limit=20))
print(client.list_queues())
```

The CLI exposes the same operations. Configure `FLUXQUEUE_URL` and `FLUXQUEUE_API_KEY`, or pass `--base-url` and `--api-key`:

```bash
fluxqueue submit --json '{"task_type":"echo","payload":{"message":"hello"}}'
fluxqueue get JOB_ID
fluxqueue list --status queued --limit 20
fluxqueue cancel JOB_ID
fluxqueue queues
```

For production, the SDK requires HTTPS for non-local hosts; plain HTTP is accepted only for loopback development addresses. Do not put API keys in command history on shared machines; prefer environment variables or a secret manager. SDK HTTP errors raise `FluxQueueError`, which exposes the HTTP `status_code` when available.

## Local development

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
pytest
ruff check .
ruff format --check .
```

Run the API with `uvicorn fluxqueue.main:app --reload` and the worker in a separate terminal with `python -m fluxqueue.worker`.

## Testing

The default test suite uses isolated SQLite databases for fast API and worker-state checks:

```bash
pytest
ruff check .
ruff format --check .
```

The PostgreSQL-only integration tests verify real row-lock skipping, simultaneous worker claims,
expired lease reclamation, and stale-token fencing. They are run automatically by the
`postgres-integration` GitHub Actions job against a disposable PostgreSQL 16 service. To run
them locally, start a disposable PostgreSQL database and set
`FLUXQUEUE_POSTGRES_TEST_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`, then run:

```bash
pytest -q tests/test_postgres_integration.py
```

Do not point these integration tests at a database containing data you need to keep: the fixture
creates and drops the FluxQueue tables.

## Benchmarking

Run the included enqueue benchmark against a local or controlled deployment you own:

```bash
# PowerShell: $env:FLUXQUEUE_API_KEY = "your-test-key"
python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --requests 100 --concurrency 10
```

It reports request throughput, mean/p50/p95/p99 response latency, and HTTP status counts. It measures enqueue API latency only, not end-to-end job completion. Use a disposable environment and keep request volume below the configured active-job quota; do not run against production without an approved test window.

## Reliability boundaries

The `0002_tenant_isolation` migration assigns existing jobs to the `default` tenant, adds tenant-scoped idempotency uniqueness, and indexes tenant queue queries. The worker uses lease tokens to fence stale completion/failure writes and renews leases while a handler runs. Expired claims can be reclaimed. Execution is at-least-once: an external side effect may occur before a worker crashes and acknowledges it, so side-effecting handlers must be idempotent. SQLite is useful for local development; use PostgreSQL for multi-worker deployments and concurrency behavior.

Tenant scope is derived exclusively from the authenticated API key, never from client-supplied request data. The `0002_tenant_isolation` migration backfills existing jobs into the `default` tenant and scopes idempotency keys by tenant and queue. Edge rate limiting, key rotation/revocation, process-kill/database-outage fault injection, production secret management, and controlled load/soak benchmark evidence remain release gates; a repeatable enqueue benchmark utility is included. `MAX_ACTIVE_JOBS_PER_TENANT` limits queued, running, and retry-wait jobs per tenant (default 1000); PostgreSQL advisory locks serialize quota checks across API replicas. See [deployment readiness](docs/deployment-readiness.md) for the pre-deployment checklist and required release evidence. See the [controlled fault-injection and soak-test runbook](docs/fault-injection-and-soak-test.md) for repeatable recovery and load-test procedures. CI includes a SQLite regression test that upgrades a populated pre-tenant jobs table, checks that existing job data survives with the `default` tenant, and verifies downgrade restoration. Migration upgrade/downgrade checks and PostgreSQL row-locking integration tests must pass on the newest run before release.

## Integrations

See [developer tooling and integrations](docs/integrations.md) for GitHub Actions, Codecov, Doppler, CodeScene, Copilot, and Codex setup and verification boundaries. See the [operations runbook](docs/operations.md) for key rotation, quotas, edge policy, recovery, and benchmarking.

Codecov upload activates when the repository Actions secret `CODECOV_TOKEN` is configured. Doppler tokens must be supplied through a secret manager, never committed. CodeScene must be configured through its service UI. Configuration in documentation alone does not prove that an integration is active.

## CI status

CI runs automatically on pushes, pull requests, and a weekly schedule. It checks SQLite unit/API tests, validates Compose configuration, builds the container and verifies it runs as non-root, smoke-tests startup/health/authenticated access, archives machine-readable test reports, audits resolved Python dependencies, and runs a separate PostgreSQL service job for `SKIP LOCKED`, concurrent claims, expired-lease recovery, and stale-token fencing. The PostgreSQL job also validates the Alembic migration. Treat a release as blocked unless the latest required CI checks pass; use GitHub's native check status and uploaded test reports as evidence, not screenshots or copied logs. Codecov upload is skipped unless `CODECOV_TOKEN` is configured.

## License

MIT — see [LICENSE](LICENSE).
