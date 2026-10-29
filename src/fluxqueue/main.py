"""FastAPI service."""

from fastapi import Depends, FastAPI, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fluxqueue.auth import require_api_key
from fluxqueue.db import get_session
from fluxqueue.models import Job
from fluxqueue.schemas import JobCreate, JobList, JobRead
from fluxqueue.service import cancel_queued_job, enqueue, get_job, list_jobs

app = FastAPI(
    title="FluxQueue",
    description="Durable job submission and operational API with tenant-scoped access.",
    version="0.1.0",
)


@app.middleware("http")
async def add_security_headers(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Set baseline browser-facing headers; configure HSTS at the TLS proxy."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request, exc: RequestValidationError) -> JSONResponse:
    """Return safe validation details without echoing non-JSON input values."""
    del request
    details = [
        {
            "loc": list(error.get("loc", ())),
            "msg": str(error.get("msg", "Invalid request")),
            "type": str(error.get("type", "value_error")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def ready(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "reachable"}


@app.post(
    "/api/v1/jobs",
    response_model=JobRead,
    status_code=202,
    tags=["jobs"],
)
def create_job(
    data: JobCreate,
    tenant_id: str = Depends(require_api_key),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=255
    ),
    session: Session = Depends(get_session),
) -> JobRead:
    return JobRead.model_validate(enqueue(session, data, idempotency_key, tenant_id))


@app.get(
    "/api/v1/jobs",
    response_model=JobList,
    tags=["jobs"],
)
def get_jobs(
    tenant_id: str = Depends(require_api_key),
    status: str | None = Query(
        default=None,
        pattern="^(queued|running|succeeded|retry_wait|dead|cancelled)$",
    ),
    queue: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> JobList:
    items, total = list_jobs(
        session,
        status=status,
        queue=queue,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
    )
    return JobList(
        items=[JobRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobRead,
    tags=["jobs"],
)
def read_job(
    job_id: str,
    tenant_id: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> JobRead:
    return JobRead.model_validate(get_job(session, job_id, tenant_id))


@app.post(
    "/api/v1/jobs/{job_id}/cancel",
    response_model=JobRead,
    tags=["jobs"],
)
def cancel_job(
    job_id: str,
    tenant_id: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> JobRead:
    return JobRead.model_validate(cancel_queued_job(session, job_id, tenant_id))


@app.get("/api/v1/queues", tags=["queues"])
def get_queues(
    tenant_id: str = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> list[dict[str, object]]:
    rows = session.execute(
        select(Job.queue_name, Job.status, func.count())
        .where(Job.tenant_id == tenant_id)
        .group_by(Job.queue_name, Job.status)
    ).all()
    counts: dict[str, dict[str, int]] = {}
    for queue_name, status, count in rows:
        counts.setdefault(queue_name, {})[status] = count
    return [{"name": name, "counts": values} for name, values in sorted(counts.items())]
