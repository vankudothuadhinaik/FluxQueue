"""Runtime settings with production fail-closed checks."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./fluxqueue.db"
    log_level: str = "INFO"
    api_key: str | None = None

    @model_validator(mode="after")
    def require_api_key_in_production(self):
        if self.app_env.lower() in {"production", "prod"} and not self.api_key:
            raise ValueError("API_KEY must be configured when APP_ENV is production")
        return self


settings = Settings()
