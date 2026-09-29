"""Environment-backed settings for structured role extraction."""

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class RoleExtractionSettings(BaseSettings):
    """Configure the LLM boundary without making it required for API startup."""

    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="ROLE_EXTRACTION_",
        extra="ignore",
    )

    provider: str = "openai"
    api_key: SecretStr | None = None
    model: str = "gpt-5-mini"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_attempts: int = Field(default=3, ge=1, le=5)
    retry_base_delay_seconds: float = Field(default=0.2, ge=0, le=5)

    @field_validator("api_key")
    @classmethod
    def normalize_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Treat an empty environment placeholder as unconfigured."""

        if value is not None and not value.get_secret_value().strip():
            return None
        return value

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Allow only explicitly implemented providers."""

        normalized = value.strip().lower()
        if normalized not in {"openai", "disabled"}:
            raise ValueError("role extraction provider must be 'openai' or 'disabled'")
        return normalized

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject blank model identifiers."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("role extraction model cannot be blank")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Require HTTPS except for an explicitly local development endpoint."""

        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("role extraction base URL must be absolute HTTP(S)")
        if parsed.query or parsed.fragment:
            raise ValueError("role extraction base URL cannot contain a query or fragment")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("role extraction base URL must use HTTPS outside local development")
        return normalized
