"""Runtime settings with production fail-closed checks."""

from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: str = "development"
    database_url: str | None = None
    postgres_password: str | None = None
    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "fluxqueue"
    database_user: str = "fluxqueue"
    log_level: str = "INFO"
    api_key: str | None = None
    api_keys: dict[str, str] = Field(default_factory=dict)
    max_active_jobs_per_tenant: int = Field(default=1000, ge=1)

    @model_validator(mode="after")
    def derive_database_url(self):
        if not self.database_url:
            if self.postgres_password:
                password = quote(self.postgres_password, safe="")
                self.database_url = (
                    f"postgresql+psycopg://{quote(self.database_user, safe='')}:{password}"
                    f"@{self.database_host}:{self.database_port}/"
                    f"{quote(self.database_name, safe='')}"
                )
            else:
                self.database_url = "sqlite:///./fluxqueue.db"
        return self

    @model_validator(mode="after")
    def validate_authentication_settings(self):
        is_production = self.app_env.lower() in {"production", "prod"}
        if is_production and not (self.api_key or self.api_keys):
            raise ValueError("API_KEY or API_KEYS must be configured when APP_ENV is production")
        if any(not key for key in self.api_keys):
            raise ValueError("API_KEYS must not contain empty API keys")
        if any(not tenant or len(tenant) > 128 for tenant in self.api_keys.values()):
            raise ValueError("API_KEYS tenant identifiers must be 1 to 128 characters")
        return self


settings = Settings()
