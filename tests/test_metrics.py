"""Operational metrics remain low-cardinality and secret-free."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fluxqueue.db import Base
from fluxqueue.metrics import render


def test_metrics_endpoint_exposes_safe_fixed_names(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "fluxqueue_jobs_total" in response.text
    assert "fluxqueue_oldest_queued_job_age_seconds" in response.text
    assert "Authorization" not in response.text


def test_metrics_render_handles_sqlite_naive_timestamps():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        session = sessionmaker(bind=engine)()
        assert "fluxqueue_jobs" in render(session)
        session.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
