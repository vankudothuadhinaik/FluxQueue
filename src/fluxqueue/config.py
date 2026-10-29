"""Runtime settings with production fail-closed checks."""

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
            if not tenant_id or len(tenant_id) > 128:
                raise ValueError("API_KEYS tenant identifiers must contain 1 to 128 characters")
        return value

    @model_validator(mode="after")
    def require_api_key_in_production(self):
        if self.app_env.lower() in {"production", "prod"} and not (self.api_key or self.api_keys):
            raise ValueError("API_KEY or API_KEYS must be configured when APP_ENV is production")
        return self


settings = Settings()
