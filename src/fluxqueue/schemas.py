"""API request and response schemas."""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    task_type: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]*$"
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    queue: str = Field(
        default="default", min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    priority: int = Field(default=5, ge=0, le=9)
    max_attempts: int = Field(default=3, ge=1, le=20)

    @field_validator("payload")
    @classmethod
    def enforce_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 65_536:
            raise ValueError("payload must be at most 64 KiB when encoded as JSON")
        return value


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    queue_name: str
    task_type: str
    payload: dict[str, Any]
    status: str
    priority: int
    max_attempts: int
    attempt_count: int
    idempotency_key: str | None
    payload_fingerprint: str | None
    result_json: dict[str, Any] | None
    last_error: str | None
    run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


class JobList(BaseModel):
    items: list[JobRead]
    limit: int
    offset: int
    total: int
