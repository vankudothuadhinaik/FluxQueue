"""Add scheduling and worker lease columns."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0001_worker_leases"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "jobs" not in inspector.get_table_names():
        # Create the full current schema for new installations.
        from fluxqueue import models  # noqa: F401
        from fluxqueue.db import Base

        Base.metadata.create_all(bind=bind)
        return

    existing = {column["name"] for column in inspector.get_columns("jobs")}
    additions = [
        ("run_at", sa.DateTime(timezone=True)),
        ("locked_by", sa.String(length=128)),
        ("lease_token", sa.String(length=36)),
        ("lease_expires_at", sa.DateTime(timezone=True)),
    ]
    for name, column_type in additions:
        if name not in existing:
            op.add_column("jobs", sa.Column(name, column_type, nullable=True))

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    if "ix_jobs_status_run_at" not in indexes:
        op.create_index("ix_jobs_status_run_at", "jobs", ["status", "run_at"], unique=False)
    if "ix_jobs_status_lease_expiry" not in indexes:
        op.create_index(
            "ix_jobs_status_lease_expiry", "jobs", ["status", "lease_expires_at"], unique=False
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "jobs" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("jobs")}
    if "ix_jobs_status_lease_expiry" in indexes:
        op.drop_index("ix_jobs_status_lease_expiry", table_name="jobs")
    if "ix_jobs_status_run_at" in indexes:
        op.drop_index("ix_jobs_status_run_at", table_name="jobs")
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    for name in ("lease_expires_at", "lease_token", "locked_by", "run_at"):
        if name in columns:
            op.drop_column("jobs", name)
