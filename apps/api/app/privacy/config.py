"""Environment-backed privacy and retention policy settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class PrivacySettings(BaseSettings):
    """Configure the short pilot retention window and bounded cleanup batch."""

    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="PRIVACY_",
        extra="ignore",
    )

    retention_days: int = Field(default=90, ge=1, le=3650)
    retention_batch_size: int = Field(default=100, ge=1, le=1000)
