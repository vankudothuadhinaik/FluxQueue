"""Shared API-key authentication for protected API routes."""

from secrets import compare_digest

from fastapi import Header, HTTPException

from fluxqueue.config import settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """Require a bearer API key when configured; production configuration fails closed."""
    expected = settings.api_key
    if not expected:
        if settings.app_env.lower() in {"production", "prod"}:
            raise HTTPException(status_code=503, detail="API authentication is not configured")
        return

    scheme, separator, provided = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
