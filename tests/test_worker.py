"""Worker lease and state-transition tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fluxqueue.db import Base
from fluxqueue.models import Job, JobStatus
from fluxqueue.worker import claim_next_job, complete_job, fail_job, renew_lease


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        yield db
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def add_job(session, *, task_type="echo", priority=5, max_attempts=3):
    job = Job(
        task_type=task_type,
        payload={"message": "hello"},
        priority=priority,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_claim_increments_attempt_and_sets_lease(session):
    job = add_job(session)
    claimed = claim_next_job(session, "worker-a", lease_seconds=30)
    assert claimed is not None
    stored = session.get(Job, job.id)
    assert stored.status == JobStatus.RUNNING.value
    assert stored.attempt_count == 1
    assert stored.locked_by == "worker-a"
    assert stored.lease_token == claimed["lease_token"]
    assert stored.lease_expires_at is not None


def test_success_requires_current_lease_token(session):
    job = add_job(session)
    claimed = claim_next_job(session, "worker-a")
    assert claimed is not None
    assert complete_job(session, job.id, "stale-token", {"ok": True}) is False
    assert complete_job(session, job.id, claimed["lease_token"], {"ok": True}) is True
    stored = session.get(Job, job.id)
    assert stored.status == JobStatus.SUCCEEDED.value
    assert stored.result_json == {"ok": True}
    assert stored.lease_token is None


def test_expired_lease_can_be_reclaimed_and_old_token_is_fenced(session):
    job = add_job(session, max_attempts=3)
    first = claim_next_job(session, "worker-a", lease_seconds=-1)
    assert first is not None
    second = claim_next_job(session, "worker-b", lease_seconds=30)
    assert second is not None
    assert second["id"] == job.id
    assert second["lease_token"] != first["lease_token"]
    assert complete_job(session, job.id, first["lease_token"], {"stale": True}) is False
    assert complete_job(session, job.id, second["lease_token"], {"fresh": True}) is True


def test_failed_job_enters_retry_wait_then_can_be_claimed(session):
    job = add_job(session, max_attempts=2)
    first = claim_next_job(session, "worker-a")
    assert first is not None
    state = fail_job(
        session,
        job.id,
        first["lease_token"],
        "temporary failure",
        retry_base_seconds=0,
        retry_max_seconds=0,
        jitter=False,
    )
    assert state == JobStatus.RETRY_WAIT.value
    second = claim_next_job(session, "worker-b")
    assert second is not None
    assert second["attempt_count"] == 2
    assert (
        fail_job(session, job.id, second["lease_token"], "again", jitter=False)
        == JobStatus.DEAD.value
    )
    assert session.get(Job, job.id).status == JobStatus.DEAD.value


def test_retry_and_completion_reject_stale_worker(session):
    job = add_job(session)
    first = claim_next_job(session, "worker-a", lease_seconds=-1)
    assert first is not None
    second = claim_next_job(session, "worker-b")
    assert second is not None
    assert fail_job(session, job.id, first["lease_token"], "late failure") is None
    assert renew_lease(session, job.id, second["lease_token"], lease_seconds=30) is True
    assert session.scalar(select(Job.status).where(Job.id == job.id)) == JobStatus.RUNNING.value


def test_priority_zero_is_claimed_before_priority_nine(session):
    low = add_job(session, priority=9)
    high = add_job(session, priority=0)
    claimed = claim_next_job(session, "worker")
    assert claimed is not None
    assert claimed["id"] == high.id
    assert session.get(Job, low.id).status == JobStatus.QUEUED.value


def test_retry_delay_prevents_early_reclaim(session):
    job = add_job(session, max_attempts=3)
    claimed = claim_next_job(session, "worker-a")
    assert claimed is not None
    assert (
        fail_job(
            session,
            job.id,
            claimed["lease_token"],
            "temporary",
            retry_base_seconds=60,
            retry_max_seconds=60,
            jitter=False,
        )
        == JobStatus.RETRY_WAIT.value
    )
    assert claim_next_job(session, "worker-b") is None


def test_expired_final_attempt_is_dead_lettered(session):
    job = add_job(session, max_attempts=1)
    claimed = claim_next_job(session, "worker-a", lease_seconds=-1)
    assert claimed is not None
    assert claim_next_job(session, "worker-b") is None
    stored = session.get(Job, job.id)
    assert stored.status == JobStatus.DEAD.value
    assert stored.lease_token is None


def test_only_registered_task_handlers_are_available():
    from fluxqueue.worker import HANDLERS

    assert set(HANDLERS) == {"echo", "add_numbers", "uppercase"}
    assert HANDLERS["add_numbers"]({"numbers": [1, 2, 3]}) == {"sum": 6}
    assert HANDLERS["uppercase"]({"text": "fluxqueue"}) == {"text": "FLUXQUEUE"}
    with pytest.raises(ValueError):
        HANDLERS["add_numbers"]({"numbers": ["__import__('os')"]})


def test_future_scheduled_job_is_not_claimed_early(session):
    job = add_job(session)
    job.run_at = datetime.now(UTC) + timedelta(seconds=60)
    session.commit()
    assert claim_next_job(session, "worker-a") is None
    assert session.get(Job, job.id).status == JobStatus.QUEUED.value


def test_worker_logs_job_lifecycle_without_logging_payload(monkeypatch, caplog):
    import logging

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from fluxqueue import worker

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    with factory() as db:
        add_job(db)
        job = db.scalar(select(Job))
        assert job is not None
        job.payload = {"message": "private-payload-marker"}
        db.commit()

    caplog.set_level(logging.INFO, logger="fluxqueue.worker")
    try:
        assert worker.run_once(worker_id="test-worker")
        assert "Claimed job" in caplog.text
        assert "completed successfully" in caplog.text
        assert "private-payload-marker" not in caplog.text
    finally:
        engine.dispose()


def test_run_once_persists_handler_failure_without_logging_payload(monkeypatch, caplog):
    import logging

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from fluxqueue import worker

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", factory)

    def fail_handler(payload):
        raise RuntimeError("deliberate handler failure")

    monkeypatch.setitem(worker.HANDLERS, "fail_for_test", fail_handler)
    with factory() as db:
        job = Job(
            task_type="fail_for_test",
            payload={"secret_marker": "do-not-log-this"},
            max_attempts=2,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    caplog.set_level(logging.WARNING, logger="fluxqueue.worker")
    try:
        assert worker.run_once(worker_id="failure-test-worker")
        with factory() as db:
            stored = db.get(Job, job_id)
            assert stored is not None
            assert stored.status == JobStatus.RETRY_WAIT.value
            assert stored.attempt_count == 1
            assert "RuntimeError" in stored.last_error
            assert "deliberate handler failure" in stored.last_error
        assert "deliberate handler failure" not in caplog.text
        assert "do-not-log-this" not in caplog.text
    finally:
        engine.dispose()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True])
def test_add_numbers_rejects_non_finite_values_and_booleans(value):
    from fluxqueue.worker import HANDLERS

    with pytest.raises(ValueError, match="finite numbers"):
        HANDLERS["add_numbers"]({"numbers": [1, value]})


def test_add_numbers_rejects_overflowed_sum():
    from fluxqueue.worker import HANDLERS

    with pytest.raises(ValueError, match="sum must be finite"):
        HANDLERS["add_numbers"]({"numbers": [1e308, 1e308]})
