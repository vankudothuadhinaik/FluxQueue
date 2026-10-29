"""Database engine and request-scoped sessions."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fluxqueue.config import settings


class Base(DeclarativeBase):
    """Declarative model base."""


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
if settings.database_sslmode:
    connect_args["sslmode"] = settings.database_sslmode
for name in ("sslrootcert", "sslcert", "sslkey"):
    value = getattr(settings, f"database_{name}")
    if value:
        connect_args[name] = value
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped session."""
    with SessionLocal() as session:
        yield session
