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
