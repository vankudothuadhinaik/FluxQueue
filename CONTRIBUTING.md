# Contributing to FluxQueue

Thanks for helping improve FluxQueue. Changes should preserve tenant isolation, durable job acceptance, lease fencing, and the documented at-least-once execution model.

## Development setup

Requirements: Python 3.12+, Docker, and Docker Compose.

```bash
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e '.[dev]'
alembic upgrade head
pytest
ruff check .
ruff format --check .
docker compose config --quiet
docker build -t fluxqueue-dev .
```

PowerShell activation:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the API and worker in separate terminals:

```bash
uvicorn fluxqueue.main:app --reload
python -m fluxqueue.worker
```

For PostgreSQL-specific locking and concurrency tests, use a disposable PostgreSQL instance and set `FLUXQUEUE_POSTGRES_TEST_URL`. The integration fixture creates and drops FluxQueue tables; never point it at data you need to preserve.

## Engineering expectations

- Add regression tests for bug fixes and tests for new behavior.
- Preserve tenant scoping in every job read, mutation, count, and idempotency lookup.
- Use PostgreSQL integration tests for behavior that depends on row locks or advisory locks; SQLite does not prove multi-replica correctness.
- Keep credentials, job payloads, and secrets out of logs, fixtures, screenshots, and commits.
- Keep handlers idempotent when they perform external side effects; jobs are delivered at least once, not exactly once.
- Document migration behavior and verify upgrade/downgrade paths when changing the schema.
- Update README and operational documentation when API behavior, configuration, or release gates change.
- Do not claim performance or security validation without recorded, reproducible evidence.

## Pull request checklist

- [ ] Tests cover the change and pass locally.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] Migrations work from both a fresh database and the supported prior schema.
- [ ] Tenant boundaries, retries, idempotency, and stale-lease behavior remain correct.
- [ ] Documentation and `.env.example` are updated when applicable.
- [ ] No secrets, private data, or generated build artifacts are committed.
- [ ] CI, PostgreSQL integration, dependency audit, and CodeQL results have been reviewed.

GitHub Actions is the source of truth for repository CI. A local pass is not a substitute for reviewing the latest required checks.
