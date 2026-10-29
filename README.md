# FluxQueue

A durable job-processing platform built with FastAPI and PostgreSQL.

> **Status: early foundation.** The API persists and inspects jobs. Worker execution, retry scheduling, fencing, authentication, dashboard, SDK/CLI, and production migration support are not yet implemented. Treat those as planned work, not current guarantees.

## Current capabilities

- Validated job submission and commit-before-acceptance.
- Queue-scoped idempotency keys with conflict detection.
- Job retrieval, filtering, pagination, and queue counts.
- Queued-job cancellation and health/readiness checks.
- SQLAlchemy model, Docker Compose, CI, tests, Ruff, CodeQL, and optional Codecov reporting.

## Quick start

Requirements: Python 3.12+, Docker, Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000/docs.

```bash
curl -X POST http://localhost:8000/api/v1/jobs -H 'content-type: application/json' -H 'Idempotency-Key: demo-001' -d '{"task_type":"echo","payload":{"message":"hello FluxQueue"},"queue":"default","priority":5,"max_attempts":3}'
```

The default local configuration uses SQLite for a smoke test; Compose configures PostgreSQL. No task handler is executed by the API at this stage.

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
pytest
ruff check .
ruff format --check .
```

## Integrations

Codecov upload runs when the repository Actions secret `CODECOV_TOKEN` is configured. Doppler can inject runtime secrets when configured with a project/config and token; do not commit tokens. Set up CodeScene from its service UI using this repository. These integrations are not considered active merely because workflow or documentation configuration exists.

## Reliability boundary

A job queue alone cannot guarantee exactly-once external effects. A worker may perform an external action and crash before acknowledging success. Side-effecting handlers must be idempotent. See `docs/architecture.md`, `docs/failure-model.md`, and `SECURITY.md`.

## License

MIT — see [LICENSE](LICENSE).
