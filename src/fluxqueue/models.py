"""Persistent job model and lifecycle states."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from fluxqueue.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    DEAD = "dead"
    CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "queue_name", "idempotency_key", name="uq_jobs_tenant_queue_idempotency"
        ),
        Index("ix_jobs_tenant_queue_status_created", "tenant_id", "queue_name", "status", "created_at"),
        Index("ix_jobs_queue_status_created", "queue_name", "status", "created_at"),
        Index("ix_jobs_status_run_at", "status", "run_at"),
        Index("ix_jobs_status_lease_expiry", "status", "lease_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    queue_name: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED.value, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
