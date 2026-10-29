"""Runtime settings with production fail-closed checks."""

import re

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./fluxqueue.db"
    log_level: str = "INFO"
    api_key: str | None = None
    api_keys: dict[str, str] = Field(default_factory=dict)

    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, value: dict[str, str]) -> dict[str, str]:
        for tenant_id in value.values():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", tenant_id):
                raise ValueError(
                    "API_KEYS tenant identifiers must use 1-128 letters, numbers, dots, "
                    "underscores, or hyphens"
                )
        return value

    @model_validator(mode="after")
    def require_api_key_in_production(self):
        is_production = self.app_env.lower() in {"production", "prod"}
        if is_production and not (self.api_key or self.api_keys):
            raise ValueError("API_KEY or API_KEYS must be configured when APP_ENV is production")
        if is_production and self.api_key and self.api_keys:
            raise ValueError("Configure API_KEYS for tenant isolation or API_KEY for single-tenant use, not both")
        return self


settings = Settings()
