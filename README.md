# FluxQueue

[![CI](https://github.com/vankudothuadhinaik/FluxQueue/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vankudothuadhinaik/FluxQueue/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A durable job-processing platform built with FastAPI, SQLAlchemy, and PostgreSQL.

> **Current status (2026-10-30):** Docker-first local staging passed, and CI for PR #17 passed at [run 40936739361](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40936739361), head `78f89b0`. Test, PostgreSQL integration, dependency audit, and security jobs passed; Codecov upload is included in the test job. The PR remains open and unmerged. These results do not establish production readiness.

## Current capabilities

- Validated job submission with a 64 KiB serialized-payload cap and commit-before-acceptance.
- Tenant-scoped API keys and tenant-isolated job reads, listings, cancellation, queue counts, and idempotency keys. When `API_KEYS` is non-empty, it takes precedence over the legacy single-tenant `API_KEY`.
- Job retrieval, filtering, pagination, queue counts, and cancellation.
- Separate worker process with registered handlers: `echo`, `add_numbers`, and `uppercase`.
- Lease expiry/reclaim, heartbeat renewal, stale-token fencing, bounded exponential retry, terminal `dead` state, and payload-free worker lifecycle logs.
- Non-root API/worker container, baseline security response headers, loopback-bound local Compose ports, Alembic migrations, SQLite unit/API tests, PostgreSQL concurrency integration tests, container startup/auth smoke checks, low-cardinality `/metrics`, Ruff, CodeQL, automated dependency auditing, Dependabot, and optional Codecov.
- Doppler-to-Compose environment validation, secret-safe diagnostics, and URL-encoded PostgreSQL credentials.
- Example Nginx edge policy with explicit TLS 1.2/1.3 defaults, disabled server tokens, request-size limits, and per-IP API rate limiting.

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

### Doppler-backed Compose startup

Configure Doppler project `fluxqueue`, config `dev`, and at least `POSTGRES_PASSWORD`, `APP_ENV`, and `API_KEYS`; `MAX_ACTIVE_JOBS_PER_TENANT` is optional. Authenticate using the Doppler CLI, then run from the repository root:

```bash
doppler login
doppler setup --no-interactive
doppler run -- python scripts/validate_doppler_config.py --require-doppler-env
doppler run -- docker compose up --build -d
curl --fail http://127.0.0.1:8000/health/ready
docker compose ps
```

The API and worker receive the same resolved database/application environment, while PostgreSQL receives `POSTGRES_PASSWORD`. The validator checks this wiring and emits only variable names and safe diagnostics. Do not print or commit secret values.

For managed PostgreSQL, set `DATABASE_SSLMODE=verify-full` (preferred) or `verify-ca` and provide `DATABASE_SSLROOTCERT` through the secret/file provisioning system. Optional `DATABASE_SSLCERT` and `DATABASE_SSLKEY` support mutual TLS. Production configuration fails fast unless PostgreSQL is configured with certificate-verified TLS; local SQLite and development Compose remain available for development.

### Docker-first local staging smoke test

Use an isolated Compose project and loopback port for disposable staging validation. The command below uses test-only credentials:

```powershell
$env:FLUXQUEUE_API_PORT = "18005"
$env:POSTGRES_PASSWORD = "docker-staging-password"
$env:API_KEY = "docker-staging-test-key"
$env:APP_ENV = "development"
docker compose -p fluxqueue-staging up -d --build
curl.exe --fail http://127.0.0.1:18005/health/ready
docker compose -p fluxqueue-staging ps
```

Verify liveness/readiness, protected-route responses, a harmless authenticated job, `/metrics`, worker logs, and restart recovery. Stop only this isolated project with `docker compose -p fluxqueue-staging down`; this preserves the disposable `fluxqueue-staging_postgres_data` volume. The image excludes tests, docs, local environments, caches, and Git metadata through `.dockerignore` and runs as UID/GID `10001:10001`.

## API

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/queues`
- `GET /health/live` and `GET /health/ready`
- `GET /metrics` (keep this endpoint on a private monitoring network; it exposes aggregate counts, not payloads or credentials)

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

The PostgreSQL-only integration tests verify real row-lock skipping, simultaneous worker claims, expired lease reclamation, and stale-token fencing. They run automatically in the `postgres-integration` GitHub Actions job against a disposable PostgreSQL 16 service. To run locally, start a disposable PostgreSQL database and set `FLUXQUEUE_POSTGRES_TEST_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`, then run:

```bash
pytest -q tests/test_postgres_integration.py
```

Do not point these integration tests at a database containing data you need to keep: the fixture creates and drops the FluxQueue tables.

## Benchmarking

Run the included enqueue benchmark against a local or controlled deployment you own:

```bash
# PowerShell: $env:FLUXQUEUE_API_KEY = "your-test-key"
python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --requests 100 --concurrency 10
```

It reports request throughput, mean/p50/p95/p99 response latency, and HTTP status counts. It measures enqueue API latency only, not end-to-end job completion. Use a disposable environment and keep request volume below the configured active-job quota; do not run against production without an approved test window.

## Reliability boundaries

The `0002_tenant_isolation` migration assigns existing jobs to the `default` tenant, adds tenant-scoped idempotency uniqueness, and indexes tenant queue queries. The worker uses lease tokens to fence stale completion/failure writes and renews leases while a handler runs. Expired claims can be reclaimed. Execution is at-least-once: an external side effect may occur before a worker crashes and acknowledges it, so side-effecting handlers must be idempotent. SQLite is useful for local development; use PostgreSQL for multi-worker deployments and concurrency behavior.

Tenant scope is derived exclusively from the authenticated API key, never from client-supplied request data. `MAX_ACTIVE_JOBS_PER_TENANT` limits queued, running, and retry-wait jobs per tenant (default 1000); PostgreSQL advisory locks serialize quota checks across API replicas. See [deployment readiness](docs/deployment-readiness.md) for the pre-deployment checklist and required release evidence, [controlled fault-injection and soak-test runbook](docs/fault-injection-and-soak-test.md) for recovery/load-test procedures, and [operations runbook](docs/operations.md) for key rotation, quotas, edge policy, recovery, and benchmarking.

## Integrations

See [developer tooling and integrations](docs/integrations.md) for GitHub Actions, Codecov, Doppler, CodeScene, Copilot, and Codex setup and verification boundaries.

Codecov upload activates when the repository Actions secret `CODECOV_TOKEN` is configured. A successful upload does not prove an exposed credential was revoked; confirm rotation and revocation in Codecov/GitHub settings. Doppler tokens must be supplied through a secret manager, never committed. CodeScene must be configured through its service UI. Documentation alone does not prove an integration is active.

## CI status and latest verification

The latest verified CI run for PR #17 is [40936739361](https://github.com/vankudothuadhinaik/FluxQueue/actions/runs/40936739361), for commit `78f89b0` on `feat/doppler-integration`. All four jobs passed:

- `test`: compilation, migration checks, Ruff, unit/API tests, Compose and Doppler wiring validation, Docker build, non-root check, container smoke test, and Codecov upload. The workflow also syntax-checks the example Nginx configuration with a temporary self-signed certificate; this does not verify a real certificate, public TLS, or live proxy routing.
- `postgres-integration`: PostgreSQL migration, locking, and lease-fencing checks.
- `dependency-audit`: resolved Python dependency audit.
- `security`: CodeQL analysis and SARIF publication.

The Docker-first local staging run and its detailed checks are recorded above and in [developer tooling and integrations](docs/integrations.md). Earlier local verification recorded 73 passed and 4 skipped, plus 4 PostgreSQL integration tests passed; those local results are historical and are not claimed as freshly rerun during the final documentation update.

## Production readiness: still outstanding

**CI and local Docker success do not make FluxQueue production-ready.** The following deployment-owner gates remain open:

- Confirm Codecov credential rotation/revocation in provider settings; the replacement upload succeeded in CI, but secret values cannot be read back through GitHub.
- Validate Nginx syntax, certificates, TLS negotiation, and proxy behavior in an authorized disposable environment. The example is a starting point; `limit_req_zone` belongs in the Nginx `http {}` context.
- Verify managed PostgreSQL TLS, network restrictions, least-privilege credentials, backup restoration, and migration rollback against production-like data.
- Exercise database outages, worker termination during handlers, lease expiry, retry exhaustion, and restart recovery.
- Verify idempotency for every external side-effecting handler.
- Configure and verify operational metrics, structured logs, alerts, on-call ownership, resource limits, log retention, and rollback procedures.
- Run controlled load and soak tests; record throughput, latency percentiles, worker concurrency, and database utilization.
- Implement and test API-key rotation/revocation workflow; self-service key management is not implemented.

Track evidence in [deployment readiness](docs/deployment-readiness.md). No cloud staging environment has been provisioned, and PR #17 remains open and unmerged.
  
## License

MIT — see [LICENSE](LICENSE).
