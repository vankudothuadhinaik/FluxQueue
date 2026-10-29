# FluxQueue

A durable job-processing platform built with FastAPI and PostgreSQL.

> **Status:** initial foundation. The README distinguishes implemented behavior from planned worker/recovery features; do not treat the roadmap as production guarantees.

## Quick start

Requirements: Python 3.12+, Docker, Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000/docs. Submit a job:

```bash
curl -X POST http://localhost:8000/api/v1/jobs -H "content-type: application/json" -H "Idempotency-Key: demo-001" -d '{"task_type":"echo","payload":{"message":"hello FluxQueue"},"queue":"default","priority":5,"max_attempts":3}'
```

The initial API persists and inspects jobs; it does not yet run task handlers or guarantee worker crash recovery. SQLite is the default for local smoke tests. Compose configures PostgreSQL.

## Included

- Validated job submission and durable database commit before response.
- Queue-scoped idempotency keys and conflict detection.
- Paginated/filterable jobs, queue counts, health/readiness endpoints.
- Queued-job cancellation and explicit lifecycle states.
- Docker Compose, CI tests, Ruff checks, CodeQL, optional Codecov upload.
- Architecture, failure-model, contribution, and security documentation.

## API

- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/queues`
- `GET /health/live`, `GET /health/ready`

## Local development

```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
```

See `docs/architecture.md` and `docs/failure-model.md`. Exactly-once external side effects cannot be guaranteed by a queue alone; handlers with side effects must be idempotent.

## Integrations

Codecov upload activates if `CODECOV_TOKEN` is configured in repository Actions secrets. Doppler can be used to inject runtime secrets, but no Doppler token is committed. CodeScene integration should be enabled from its service using the repository URL and its current documented setup.

## License

MIT. See [LICENSE](LICENSE).
