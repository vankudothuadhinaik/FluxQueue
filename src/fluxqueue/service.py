"""Job operations and idempotency rules."""

import hashlib
import json
from datetime import UTC, datetime
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fluxqueue.models import Job, JobStatus
from fluxqueue.schemas import JobCreate


class JobPage(NamedTuple):
    items: list[Job]
    total: int


def fingerprint(data: JobCreate) -> str:
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enqueue(session: Session, data: JobCreate, idempotency_key: str | None) -> Job:
    digest = fingerprint(data)
    if idempotency_key:
        existing = session.scalar(
            select(Job).where(
                Job.queue_name == data.queue,
                Job.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.payload_fingerprint != digest:
                raise HTTPException(status_code=409, detail="Idempotency key reused with different request")
            return existing

    job = Job(
        queue_name=data.queue,
        task_type=data.task_type,
        payload=data.payload,
        priority=data.priority,
        max_attempts=data.max_attempts,
        idempotency_key=idempotency_key,
        payload_fingerprint=digest,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if idempotency_key:
            existing = session.scalar(
                select(Job).where(
                    Job.queue_name == data.queue,
                    Job.idempotency_key == idempotency_key,
                )
            )
            if existing and existing.payload_fingerprint == digest:
                return existing
        raise HTTPException(status_code=409, detail="Conflicting idempotency key") from exc
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def list_jobs(
    session: Session,
    *,
    status: str | None,
    queue: str | None,
    limit: int,
    offset: int,
) -> JobPage:
    query = select(Job)
    count_query = select(func.count()).select_from(Job)
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    if queue:
        query = query.where(Job.queue_name == queue)
        count_query = count_query.where(Job.queue_name == queue)
    total = session.scalar(count_query) or 0
    items = session.scalars(
        query.order_by(Job.created_at.desc(), Job.id).limit(limit).offset(offset)
    ).all()
    return JobPage(items=list(items), total=total)


def cancel_queued_job(session: Session, job_id: str) -> Job:
    now = datetime.now(UTC)
    result = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
        )
        .values(
            status=JobStatus.CANCELLED.value,
            finished_at=now,
            updated_at=now,
            run_at=None,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        job = get_job(session, job_id)
        raise HTTPException(status_code=409, detail=f"Cannot cancel job in state '{job.status}'")
    session.commit()
    return get_job(session, job_id)
