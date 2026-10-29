"""Runtime configuration safety checks."""

from fluxqueue.config import Settings


def test_database_password_is_url_encoded_when_compose_builds_url(monkeypatch):
    # CI sets DATABASE_URL globally for the SQLite test suite; clear it so this
    # focused test exercises the PostgreSQL URL derived from the supplied secret.
    monkeypatch.delenv("DATABASE_URL", raising=False)
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


def test_production_requires_a_database_configuration():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DATABASE_URL or POSTGRES_PASSWORD"):
        Settings(app_env="production", api_key="test-key")


def test_production_postgres_requires_certificate_verified_tls():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DATABASE_SSLMODE"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://db.example/fluxqueue",
            api_key="test-key",
        )


def test_configuration_errors_do_not_echo_secret_values():
    import pytest
    from pydantic import ValidationError

    secret = "do-not-echo-this-secret"
    with pytest.raises(ValidationError) as error:
        Settings(api_keys={secret: ""})

    assert secret not in str(error.value)
