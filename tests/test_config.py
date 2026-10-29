"""Runtime configuration safety checks."""

from fluxqueue.config import Settings


def test_database_password_is_url_encoded_when_compose_builds_url():
    configured = Settings(postgres_password="p@ss:word/with?chars#")

    assert configured.database_url == (
        "postgresql+psycopg://fluxqueue:p%40ss%3Aword%2Fwith%3Fchars%23@db:5432/fluxqueue"
    )


def test_explicit_database_url_takes_precedence_over_compose_components():
    configured = Settings(
        database_url="postgresql+psycopg://external.example/fluxqueue",
        postgres_password="unused",
    )

    assert configured.database_url == "postgresql+psycopg://external.example/fluxqueue"
