"""Regression tests for upgrading existing job data to tenant isolation."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    inspect,
    select,
    text,
)


def _legacy_jobs_table(engine):
    metadata = MetaData()
    jobs = Table(
        "jobs",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("queue_name", String(128), nullable=False, server_default="default"),
        Column("task_type", String(128), nullable=False),
        Column("payload", JSON, nullable=False),
        Column("status", String(32), nullable=False),
        Column("priority", Integer, nullable=False),
        Column("max_attempts", Integer, nullable=False),
        Column("attempt_count", Integer, nullable=False),
        Column("idempotency_key", String(255)),
        Column("payload_fingerprint", String(64)),
        Column("result_json", JSON),
        Column("last_error", String),
        Column("run_at", DateTime(timezone=True)),
        Column("locked_by", String(128)),
        Column("lease_token", String(36)),
        Column("lease_expires_at", DateTime(timezone=True)),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("finished_at", DateTime(timezone=True)),
        UniqueConstraint("queue_name", "idempotency_key", name="uq_jobs_queue_idempotency"),
    )
    metadata.create_all(engine)
    return jobs



def test_tenant_migration_preserves_existing_jobs_and_scopes_idempotency():
    engine = create_engine("sqlite://")
    jobs = _legacy_jobs_table(engine)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            jobs.insert().values(
                id="legacy-job",
                queue_name="mail",
                task_type="echo",
                payload={"message": "keep me"},
                status="queued",
                priority=5,
                max_attempts=3,
                attempt_count=0,
                idempotency_key="legacy-key",
                payload_fingerprint="fingerprint",
                created_at=now,
                updated_at=now,
            )
        )
        context = MigrationContext.configure(connection)
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "0002_tenant_isolation.py"
        )
        spec = importlib.util.spec_from_file_location("tenant_migration", migration_path)
        assert spec is not None and spec.loader is not None
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(context):
            migration.upgrade()

        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("jobs")}
        assert "tenant_id" in columns
        constraints = {
            item.get("name") for item in inspector.get_unique_constraints("jobs")
        }
        assert "uq_jobs_tenant_queue_idempotency" in constraints
        assert "uq_jobs_queue_idempotency" not in constraints

        row = connection.execute(select(jobs.c.id, jobs.c.payload)).one()
        assert row.id == "legacy-job"
        assert row.payload == {"message": "keep me"}
        tenant_id = connection.execute(text("SELECT tenant_id FROM jobs")).scalar_one()
        assert tenant_id == "default"

        with Operations.context(context):
            migration.downgrade()
        inspector = inspect(connection)
        columns_after_downgrade = {
            column["name"] for column in inspector.get_columns("jobs")
        }
        assert "tenant_id" not in columns_after_downgrade
        constraints_after_downgrade = {
            item.get("name") for item in inspector.get_unique_constraints("jobs")
        }
        assert "uq_jobs_queue_idempotency" in constraints_after_downgrade
        assert connection.execute(select(jobs.c.id)).scalar_one() == "legacy-job"
    engine.dispose()
