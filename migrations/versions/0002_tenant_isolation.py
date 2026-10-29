"""Add tenant ownership and isolate idempotency keys by tenant."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_tenant_isolation"
down_revision = "0001_worker_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("jobs")}
    constraints = {
        constraint.get("name") for constraint in inspector.get_unique_constraints("jobs")
    }

    if "tenant_id" not in columns:
        with op.batch_alter_table("jobs") as batch:
            batch.add_column(
                sa.Column(
                    "tenant_id",
                    sa.String(length=128),
                    nullable=False,
                    server_default="default",
                )
            )
            if "uq_jobs_queue_idempotency" in constraints:
                batch.drop_constraint("uq_jobs_queue_idempotency", type_="unique")
            if "uq_jobs_tenant_queue_idempotency" not in constraints:
                batch.create_unique_constraint(
                    "uq_jobs_tenant_queue_idempotency",
                    ["tenant_id", "queue_name", "idempotency_key"],
                )

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    if "ix_jobs_tenant_queue_status_created" not in indexes:
        op.create_index(
            "ix_jobs_tenant_queue_status_created",
            "jobs",
            ["tenant_id", "queue_name", "status", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "jobs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "tenant_id" not in columns:
        return

    indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    with op.batch_alter_table("jobs") as batch:
        if "ix_jobs_tenant_queue_status_created" in indexes:
            batch.drop_index("ix_jobs_tenant_queue_status_created")
        constraints = {
            constraint.get("name") for constraint in inspector.get_unique_constraints("jobs")
        }
        if "uq_jobs_tenant_queue_idempotency" in constraints:
            batch.drop_constraint("uq_jobs_tenant_queue_idempotency", type_="unique")
        if "uq_jobs_queue_idempotency" not in constraints:
            batch.create_unique_constraint(
                "uq_jobs_queue_idempotency",
                ["queue_name", "idempotency_key"],
            )
        batch.drop_column("tenant_id")
