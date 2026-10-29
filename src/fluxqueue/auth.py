"""Bearer API-key authentication with tenant identity."""

from secrets import compare_digest

from fastapi import Header, HTTPException

from fluxqueue.config import settings


def require_api_key(authorization: str | None = Header(default=None)) -> str:
    """Authenticate a bearer key and return its tenant identity."""
    scheme, separator, provided = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not provided:
        if not settings.api_key and not settings.api_keys and settings.app_env.lower() not in {
            "production",
            "prod",
        }:
            return "default"
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    for candidate, tenant_id in settings.api_keys.items():
        if tenant_id and len(tenant_id) <= 128 and compare_digest(provided, candidate):
            return tenant_id

    expected = settings.api_key
    if expected and not settings.api_keys and compare_digest(provided, expected):
        return "default"

    if not expected and not settings.api_keys and settings.app_env.lower() not in {
        "production",
        "prod",
    }:
        return "default"

    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
