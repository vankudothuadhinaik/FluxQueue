"""Worker claim, lease, completion, and retry primitives."""

import logging
import os
import random
import socket
import time
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from fluxqueue.db import SessionLocal
from fluxqueue.models import Job, JobStatus

DEFAULT_LEASE_SECONDS = 60
MAX_RETRY_DELAY_SECONDS = 300
logger = logging.getLogger(__name__)


def claim_next_job(
    session: Session,
    worker_id: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> dict[str, Any] | None:
    """Atomically claim one eligible job; expired leases can be reclaimed."""
    now = datetime.now(UTC)
    eligible = or_(
        (
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value])
            & or_(Job.run_at.is_(None), Job.run_at <= now)
        ),
        (
            (Job.status == JobStatus.RUNNING.value)
            & Job.lease_expires_at.is_not(None)
            & (Job.lease_expires_at <= now)
        ),
    )
    job = session.scalar(
        select(Job)
        .where(eligible)
        .order_by(Job.priority.asc(), Job.created_at.asc(), Job.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    # A worker that died after exhausting its final attempt must not loop forever.
    if job.status == JobStatus.RUNNING.value and job.attempt_count >= job.max_attempts:
        job.status = JobStatus.DEAD.value
        job.last_error = job.last_error or "Worker lease expired after final attempt"
        job.finished_at = now
        job.locked_by = None
        job.lease_token = None
        job.lease_expires_at = None
        session.commit()
        return None

    token = str(uuid4())
    job.status = JobStatus.RUNNING.value
    job.attempt_count += 1
    job.locked_by = worker_id
    job.lease_token = token
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.run_at = None
    job.updated_at = now
    session.commit()
    session.refresh(job)
    return {
        "id": job.id,
        "queue_name": job.queue_name,
        "task_type": job.task_type,
        "payload": job.payload,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "lease_token": token,
    }


def renew_lease(session: Session, job_id: str, token: str, *, lease_seconds: int) -> bool:
    """Extend a lease only if this worker still owns the current token."""
    now = datetime.now(UTC)
    result = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.lease_token == token,
        )
        .values(lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now)
    )
    session.commit()
    return result.rowcount == 1


def complete_job(session: Session, job_id: str, token: str, result_json: dict[str, Any]) -> bool:
    """Acknowledge success only when the lease token still matches."""
    now = datetime.now(UTC)
    result = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.lease_token == token,
        )
        .values(
            status=JobStatus.SUCCEEDED.value,
            result_json=result_json,
            last_error=None,
            finished_at=now,
            updated_at=now,
            locked_by=None,
            lease_token=None,
            lease_expires_at=None,
            run_at=None,
        )
    )
    session.commit()
    return result.rowcount == 1


def fail_job(
    session: Session,
    job_id: str,
    token: str,
    error: str,
    *,
    retry_base_seconds: float = 1.0,
    retry_max_seconds: float = MAX_RETRY_DELAY_SECONDS,
    jitter: bool = True,
) -> str | None:
    """Record failure with bounded retry; a stale token cannot change the job."""
    job = session.scalar(
        select(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.lease_token == token,
        )
        .with_for_update()
    )
    if job is None:
        session.rollback()
        return None

    now = datetime.now(UTC)
    error_text = error[:2000]
    if job.attempt_count >= job.max_attempts:
        state = JobStatus.DEAD.value
        finished_at = now
        run_at = None
    else:
        state = JobStatus.RETRY_WAIT.value
        finished_at = None
        delay = min(
            retry_max_seconds,
            retry_base_seconds * (2 ** max(0, job.attempt_count - 1)),
        )
        if jitter and delay > 0:
            delay = random.uniform(delay * 0.5, delay)
        run_at = now + timedelta(seconds=delay)

    # Keep the token predicate in the write itself as a second fence against races.
    result = session.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.lease_token == token,
        )
        .values(
            status=state,
            last_error=error_text,
            updated_at=now,
            finished_at=finished_at,
            run_at=run_at,
            locked_by=None,
            lease_token=None,
            lease_expires_at=None,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    return state


def _echo(payload: dict[str, Any]) -> dict[str, Any]:
    return {"payload": payload}


def _add_numbers(payload: dict[str, Any]) -> dict[str, Any]:
    numbers = payload.get("numbers")
    if (
        not isinstance(numbers, list)
        or not numbers
        or any(isinstance(value, bool) or not isinstance(value, int | float) for value in numbers)
    ):
        raise ValueError("payload.numbers must be a non-empty list of numbers")
    return {"sum": sum(numbers)}


def _uppercase(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("text")
    if not isinstance(value, str):
        raise ValueError("payload.text must be a string")
    return {"text": value.upper()}


HANDLERS = {
    "echo": _echo,
    "add_numbers": _add_numbers,
    "uppercase": _uppercase,
}


def _heartbeat(job_id: str, token: str, stop: Event, lease_seconds: int) -> None:
    interval = max(1.0, lease_seconds / 3)
    while not stop.wait(interval):
        try:
            with SessionLocal() as session:
                if not renew_lease(session, job_id, token, lease_seconds=lease_seconds):
                    return
        except Exception:
            # A transient database outage should not silently kill lease renewal.
            # Keep retrying until ownership is lost or execution has stopped.
            logger.warning("Lease heartbeat failed for job %s; retrying", job_id)


def run_once(*, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
    """Claim and execute at most one job. Returns whether a job was claimed."""
    with SessionLocal() as session:
        job = claim_next_job(session, worker_id, lease_seconds=lease_seconds)
    if job is None:
        return False

    logger.info(
        "Claimed job %s (attempt %s of %s)",
        job["id"],
        job["attempt_count"],
        job["max_attempts"],
    )
    stop = Event()
    heartbeat = Thread(
        target=_heartbeat,
        args=(job["id"], job["lease_token"], stop, lease_seconds),
        daemon=True,
    )
    heartbeat.start()
    try:
        handler = HANDLERS.get(job["task_type"])
        if handler is None:
            raise ValueError(f"Unregistered task type: {job['task_type']}")
        result = handler(job["payload"])
        with SessionLocal() as session:
            completed = complete_job(session, job["id"], job["lease_token"], result)
        if completed:
            logger.info("Job %s completed successfully", job["id"])
        else:
            logger.warning("Job %s completion rejected because its lease is no longer current", job["id"])
    except Exception as exc:  # Task exceptions are persisted as job failures.
        with SessionLocal() as session:
            state = fail_job(
                session,
                job["id"],
                job["lease_token"],
                f"{type(exc).__name__}: {exc}",
            )
        if state is not None:
            logger.warning(
                "Job %s failed with %s; next state is %s",
                job["id"],
                type(exc).__name__,
                state,
            )
        else:
            logger.warning("Job %s failure rejected because its lease is no longer current", job["id"])
    finally:
        stop.set()
        heartbeat.join(timeout=2)
    return True


def main() -> None:
    """Poll until interrupted; each worker has a unique lease identity."""
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    poll_seconds = 1.0
    while True:
        try:
            if not run_once(worker_id=worker_id):
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            break
        except Exception:
            # A transient database failure should not kill the worker process.
            time.sleep(min(10.0, poll_seconds * 2))


if __name__ == "__main__":
    main()
