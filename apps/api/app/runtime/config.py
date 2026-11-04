"""Validated runtime bounds shared by local and hosted API processes."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Bound uploads without implying that hosted configuration is certified."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        env_prefix="RUNTIME_",
        extra="ignore",
    )

    max_request_body_bytes: int = Field(default=1_048_576, ge=1, le=16_777_216)
    request_body_timeout_seconds: float = Field(default=30, ge=1, le=120, allow_inf_nan=False)
