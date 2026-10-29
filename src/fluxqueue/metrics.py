"""Low-cardinality process metrics for operational scraping."""

from __future__ import annotations

from collections import Counter
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluxqueue.models import Job, JobStatus

_lock = Lock()
_counters: Counter[str] = Counter()
_durations: Counter[str] = Counter()


def increment(name: str, value: int = 1) -> None:
    """Increment a fixed-name metric without accepting user-controlled labels."""
    with _lock:
        _counters[name] += value


def observe_processing(seconds: float) -> None:
    """Record processing duration using aggregate sum/count metrics."""
    with _lock:
        _durations["count"] += 1
        _durations["sum"] += seconds


def _metric_value(name: str) -> int | float:
    with _lock:
        return _counters[name]


def render(session: Session) -> str:
    """Render Prometheus text with fixed labels and current queue gauges."""
    counts = dict(session.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    oldest_queued = session.scalar(
        select(func.min(Job.created_at)).where(Job.status == JobStatus.QUEUED.value)
    )
    lines = [
        "# HELP fluxqueue_jobs_total Jobs accepted by outcome.",
        "# TYPE fluxqueue_jobs_total counter",
        f'fluxqueue_jobs_total{{outcome="enqueued"}} {_metric_value("jobs_enqueued")}',
        f'fluxqueue_jobs_total{{outcome="completed"}} {_metric_value("jobs_completed")}',
        f'fluxqueue_jobs_total{{outcome="failed"}} {_metric_value("jobs_failed")}',
        f'fluxqueue_jobs_total{{outcome="retried"}} {_metric_value("jobs_retried")}',
        f'fluxqueue_jobs_total{{outcome="dead"}} {_metric_value("jobs_dead")}',
        "# HELP fluxqueue_job_processing_seconds Job processing duration.",
        "# TYPE fluxqueue_job_processing_seconds summary",
        f"fluxqueue_job_processing_seconds_count {_durations['count']}",
        f"fluxqueue_job_processing_seconds_sum {_durations['sum']:.6f}",
        "# HELP fluxqueue_jobs Gauge of jobs by current state.",
        "# TYPE fluxqueue_jobs gauge",
    ]
    for status in (status.value for status in JobStatus):
        lines.append(f'fluxqueue_jobs{{status="{status}"}} {counts.get(status, 0)}')
    oldest_age = 0.0
    if oldest_queued is not None:
        from datetime import UTC, datetime

        if oldest_queued.tzinfo is None:
            oldest_queued = oldest_queued.replace(tzinfo=UTC)
        oldest_age = max(0.0, (datetime.now(UTC) - oldest_queued).total_seconds())
    lines.extend(
        [
            "# HELP fluxqueue_oldest_queued_job_age_seconds Age of the oldest queued job.",
            "# TYPE fluxqueue_oldest_queued_job_age_seconds gauge",
            f"fluxqueue_oldest_queued_job_age_seconds {oldest_age:.6f}",
        ]
    )
    return "\n".join(lines) + "\n"
