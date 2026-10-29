# FluxQueue

A durable job-processing platform built with FastAPI, SQLAlchemy, and PostgreSQL.

> **Status: active foundation.** The API and a lease-based worker are implemented with starter tests. This is not yet production-hardened: authentication/tenant authorization, full fault-injection validation, and operational benchmarks remain open.

## Current capabilities

- Validated job submission with a 64 KiB serialized-payload cap and commit-before-acceptance.
- Queue-scoped idempotency keys with conflict detection.
- Job retrieval, filtering, pagination, queue counts, and cancellation.
- Separate worker process with registered handlers: `echo`, `add_numbers`, and `uppercase`.
- Lease expiry/reclaim, heartbeat renewal, stale-token fencing, bounded exponential retry, and terminal `dead` state.
- Alembic migration path, Docker Compose, SQLite unit/API tests, PostgreSQL concurrency integration tests, Ruff, CodeQL, Dependabot, and optional Codecov.

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

The Compose database password is a local-development default. Set `POSTGRES_PASSWORD` before shared use. In production, set `APP_ENV=production` and a strong `API_KEY`; startup configuration fails if the key is missing. Send it as `Authorization: Bearer <API_KEY>`. The single shared API key is not tenant-level authorization.

## API

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/queues`
- `GET /health/live` and `GET /health/ready`

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

## Reliability boundaries

The worker uses lease tokens to fence stale completion/failure writes and renews leases while a handler runs. Expired claims can be reclaimed. Execution is at-least-once: an external side effect may occur before a worker crashes and acknowledges it, so side-effecting handlers must be idempotent. SQLite is useful for local development; use PostgreSQL for multi-worker deployments and concurrency behavior.

The shared API key is not tenant isolation. Per-tenant authorization, rate limiting, process-kill/database-outage fault injection, production secret management, and reproducible performance benchmarks remain release gates. Migration upgrade/downgrade checks and PostgreSQL row-locking integration tests run in CI, but their newest run must pass before those checks are considered verified.

## Integrations

Codecov upload activates when the repository Actions secret `CODECOV_TOKEN` is configured. Doppler tokens must be supplied through a secret manager, never committed. CodeScene must be configured through its service UI. Configuration in documentation alone does not prove that an integration is active.

## CI status

CI checks SQLite unit/API tests and a separate PostgreSQL service job for `SKIP LOCKED`, concurrent claims, expired-lease recovery, and stale-token fencing. The PostgreSQL job also validates the Alembic migration. The newly added PostgreSQL job has not yet been confirmed green; verify the newest [GitHub Actions run](https://github.com/vankudothuadhinaik/FluxQueue/actions) before release. Codecov upload is skipped unless `CODECOV_TOKEN` is configured.

## License

MIT — see [LICENSE](LICENSE).
