"""PostgreSQL-only integration tests for row locking and lease recovery.

Set FLUXQUEUE_POSTGRES_TEST_URL to a disposable PostgreSQL database. SQLite tests
remain the fast default; these tests exercise PostgreSQL semantics that SQLite lacks.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from fluxqueue.db import Base
from fluxqueue.models import Job, JobStatus
from fluxqueue.worker import claim_next_job, complete_job

DATABASE_URL = os.getenv("FLUXQUEUE_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="set FLUXQUEUE_POSTGRES_TEST_URL to run PostgreSQL integration tests",
)


@pytest.fixture()
def postgres_sessions():
    """Create an isolated schema in the disposable integration-test database."""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_job(factory, message: str) -> Job:
    with factory() as session:
        job = Job(task_type="echo", payload={"message": message})
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def test_skip_locked_claims_next_available_job(postgres_sessions):
    """A locked oldest row must not block a worker from claiming the next row."""
    first = add_job(postgres_sessions, "first")
    second = add_job(postgres_sessions, "second")
    with postgres_sessions() as setup_session:
        first_row = setup_session.get(Job, first.id)
        assert first_row is not None
        first_row.created_at = datetime.now(UTC) - timedelta(days=1)
        setup_session.commit()
    locker = postgres_sessions()
    try:
        locked_job = locker.scalar(select(Job).where(Job.id == first.id).with_for_update())
        assert locked_job is not None
        with postgres_sessions() as worker_session:
            claimed = claim_next_job(worker_session, "worker-b")
        assert claimed is not None
        assert claimed["id"] == second.id
    finally:
        locker.rollback()
        locker.close()


def test_two_concurrent_workers_claim_distinct_jobs(postgres_sessions):
    """Concurrent workers should not receive the same queued job."""
    add_job(postgres_sessions, "first")
    add_job(postgres_sessions, "second")
    barrier = Barrier(2)

    def claim(worker_id: str):
        with postgres_sessions() as session:
            barrier.wait(timeout=5)
            return claim_next_job(session, worker_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, ("worker-a", "worker-b")))

    assert all(claim is not None for claim in claims)
    assert len({claim["id"] for claim in claims if claim}) == 2
    assert all(claim["attempt_count"] == 1 for claim in claims)


def test_reclaimed_lease_fences_stale_completion(postgres_sessions):
    job = add_job(postgres_sessions, "lease")
    with postgres_sessions() as session:
        first = claim_next_job(session, "worker-a", lease_seconds=-1)
    assert first is not None

    with postgres_sessions() as session:
        second = claim_next_job(session, "worker-b", lease_seconds=30)
    assert second is not None
    assert second["id"] == job.id
    assert second["lease_token"] != first["lease_token"]

    with postgres_sessions() as session:
        assert complete_job(session, job.id, first["lease_token"], {"stale": True}) is False
        assert complete_job(session, job.id, second["lease_token"], {"fresh": True}) is True
        stored = session.get(Job, job.id)
        assert stored is not None
        assert stored.status == JobStatus.SUCCEEDED.value
        assert stored.result_json == {"fresh": True}


def test_concurrent_enqueues_respect_tenant_active_job_quota(postgres_sessions, monkeypatch):
    """Tenant advisory locks prevent concurrent requests from overshooting quota."""
    from fastapi import HTTPException

    from fluxqueue.config import settings
    from fluxqueue.schemas import JobCreate
    from fluxqueue.service import enqueue

    monkeypatch.setattr(settings, "max_active_jobs_per_tenant", 1)
    barrier = Barrier(2)

    def submit(sequence: int) -> int:
        with postgres_sessions() as session:
            barrier.wait(timeout=5)
            try:
                enqueue(
                    session,
                    JobCreate(task_type="echo", payload={"sequence": sequence}),
                    f"quota-test-{sequence}",
                    "tenant-quota-test",
                )
            except HTTPException as exc:
                return exc.status_code
            return 202

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, (1, 2)))

    assert sorted(statuses) == [202, 429]
    with postgres_sessions() as session:
        active_count = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.tenant_id == "tenant-quota-test",
                Job.status.in_(
                    [
                        JobStatus.QUEUED.value,
                        JobStatus.RUNNING.value,
                        JobStatus.RETRY_WAIT.value,
                    ]
                ),
            )
        )
    assert active_count == 1
