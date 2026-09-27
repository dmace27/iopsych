"""Environment-backed settings for provider-issued internal-user tokens."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class AuthenticationSettings(BaseSettings):
    """Describe the trusted JWT issuer, audience, and HS256 verification key.

    ``jwt_secret`` is optional so operational routes can start while auth is
    not configured. Internal routes fail closed with a service error in that
    state. Hosted environments must inject the secret through their secret
    manager rather than committing it to source control.
    """

    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="AUTH_",
        extra="ignore",
    )

    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "https://auth.example.invalid"
    jwt_audience: str = "iopsych-api"
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret_strength(cls, value: SecretStr | None) -> SecretStr | None:
        """Reject short HMAC keys that do not provide 256 bits of material."""

        if value is not None and len(value.get_secret_value().encode()) < 32:
            raise ValueError("AUTH_JWT_SECRET must contain at least 32 bytes")
        return value

    @field_validator("jwt_issuer", "jwt_audience")
    @classmethod
    def validate_nonempty_identifier(cls, value: str) -> str:
        """Reject blank issuer and audience identifiers."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("authentication identifiers cannot be blank")
        return normalized
