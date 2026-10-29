"""Job operations and idempotency rules."""

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fluxqueue.models import Job, JobStatus
from fluxqueue.schemas import JobCreate


def fingerprint(data: JobCreate) -> str:
    canonical = json.dumps(data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enqueue(session: Session, data: JobCreate, idempotency_key: str | None) -> Job:
    digest = fingerprint(data)
    if idempotency_key:
        existing = session.scalar(select(Job).where(
            Job.queue_name == data.queue, Job.idempotency_key == idempotency_key
        ))
        if existing:
            if existing.payload_fingerprint != digest:
                raise HTTPException(status_code=409, detail="Idempotency key reused with different request")
            return existing

    job = Job(
        queue_name=data.queue, task_type=data.task_type, payload=data.payload,
        priority=data.priority, max_attempts=data.max_attempts,
        idempotency_key=idempotency_key, payload_fingerprint=digest,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if idempotency_key:
            existing = session.scalar(select(Job).where(
                Job.queue_name == data.queue, Job.idempotency_key == idempotency_key
            ))
            if existing and existing.payload_fingerprint == digest:
                return existing
        raise HTTPException(status_code=409, detail="Conflicting idempotency key")
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def list_jobs(session: Session, *, status: str | None, queue: str | None, limit: int, offset: int):
    query = select(Job)
    count_query = select(func.count()).select_from(Job)
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    if queue:
        query = query.where(Job.queue_name == queue)
        count_query = count_query.where(Job.queue_name == queue)
    total = session.scalar(count_query) or 0
    items = session.scalars(query.order_by(Job.created_at.desc(), Job.id).limit(limit).offset(offset)).all()
    return items, total


def cancel_queued_job(session: Session, job_id: str) -> Job:
    job = get_job(session, job_id)
    if job.status not in {JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel job in state '{job.status}'")
    job.status = JobStatus.CANCELLED.value
    job.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)
    return job
