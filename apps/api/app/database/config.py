"""Environment-backed database configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class DatabaseSettings(BaseSettings):
    """Settings used to construct the SQLAlchemy engine.

    The local default matches ``compose.yaml``. Production deployments must
    provide ``DATABASE_URL`` through their secret manager.
    """

    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://iopsych:iopsych@localhost:5432/iopsych"
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_connect_timeout_seconds: int = Field(default=5, ge=2, le=60)
    database_pool_timeout_seconds: float = Field(default=5, gt=0, le=60, allow_inf_nan=False)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_statement_timeout_ms: int = Field(default=15_000, ge=1, le=300_000)
    database_lock_timeout_ms: int = Field(default=3_000, ge=1, le=60_000)
