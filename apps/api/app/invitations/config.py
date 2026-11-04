"""Environment-backed policy and candidate-facing consent copy."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]


class InvitationSettings(BaseSettings):
    """Configure invite security, expiry, rate limits, and consent content.

    The signing key is optional so health checks can start before secrets are
    provisioned. Invite endpoints fail closed while it or delivery is absent.
    """

    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="INVITE_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    allow_synthetic_definitions: bool = False
    local_queue_enabled: bool = False
    local_queue_key: SecretStr | None = None
    local_queue_key_id: str = Field(default="local-v1", pattern=r"^[A-Za-z0-9_-]{1,64}$")

    delivery_provider: Literal["disabled", "resend"] = "disabled"
    delivery_api_key: SecretStr | None = None
    delivery_encryption_key: SecretStr | None = None
    delivery_previous_encryption_key: SecretStr | None = None
    delivery_from_email: str = "invitations@example.invalid"
    delivery_timeout_seconds: float = Field(default=10, ge=1, le=30)
    delivery_batch_size: int = Field(default=50, ge=1, le=200)
    webhook_signing_secret: SecretStr | None = None
    token_signing_secret: SecretStr | None = None
    candidate_base_url: str = "http://localhost:3000/candidate/invites"
    default_expiry_hours: int = Field(default=168, ge=1, le=720)
    maximum_expiry_hours: int = Field(default=720, ge=1, le=720)
    candidate_rate_limit: int = Field(default=30, ge=1, le=10_000)
    internal_rate_limit: int = Field(default=20, ge=1, le=10_000)
    rate_window_seconds: int = Field(default=60, ge=1, le=3_600)

    consent_notice_version: str = "pilot-v1"
    purpose_statement: str = (
        "This work-preference questionnaire helps a human interviewer prepare "
        "role-related questions. It does not make hiring decisions."
    )
    data_use_statement: str = (
        "Your responses are used only for this consented pilot and are reviewed by "
        "authorized members of the hiring team."
    )
    retention_statement: str = (
        "Pilot data is retained for {retention_days} days after submission, then anonymized."
    )
    privacy_contact_email: str = "privacy@example.invalid"
    accommodation_contact_email: str = "accommodations@example.invalid"

    @field_validator("delivery_api_key", "webhook_signing_secret")
    @classmethod
    def normalize_optional_credential(cls, value: SecretStr | None) -> SecretStr | None:
        """Treat blank secret-manager placeholders as unconfigured, never as sending keys."""
        if value is None or not value.get_secret_value().strip():
            return None
        return SecretStr(value.get_secret_value().strip())

    @field_validator("delivery_encryption_key", "delivery_previous_encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Require independent URL-safe base64-encoded 256-bit encryption keys."""
        if value is not None:
            Fernet(value.get_secret_value().encode())
        return value

    @field_validator("delivery_from_email")
    @classmethod
    def validate_sender(cls, value: str) -> str:
        """Accept a single mailbox, preventing header injection and sender lists."""
        from app.invitations.schemas import InvitationCreateRequest

        return InvitationCreateRequest.normalize_email(value.strip())

    @field_validator("token_signing_secret")
    @classmethod
    def validate_secret_strength(cls, value: SecretStr | None) -> SecretStr | None:
        """Require a full 256 bits of signing-key material when configured."""

        if value is not None and len(value.get_secret_value().encode()) < 32:
            raise ValueError("INVITE_TOKEN_SIGNING_SECRET must contain at least 32 bytes")
        return value

    @field_validator(
        "consent_notice_version",
        "purpose_statement",
        "data_use_statement",
        "retention_statement",
        "privacy_contact_email",
        "accommodation_contact_email",
    )
    @classmethod
    def validate_nonempty_text(cls, value: str) -> str:
        """Strip policy strings and reject unusable blank configuration."""

        normalized = value.strip().rstrip("/") if "://" in value else value.strip()
        if not normalized:
            raise ValueError("invitation settings cannot be blank")
        return normalized

    @field_validator("retention_statement")
    @classmethod
    def validate_retention_template(cls, value: str) -> str:
        """Keep approved disclosure copy coupled to the enforced duration."""

        if "{retention_days}" not in value:
            raise ValueError("retention statement must contain {retention_days}")
        try:
            value.format(retention_days=90)
        except (IndexError, KeyError, ValueError) as exc:
            raise ValueError("retention statement contains an invalid format field") from exc
        return value

    @field_validator("candidate_base_url")
    @classmethod
    def validate_candidate_base_url(cls, value: str) -> str:
        """Require an absolute HTTPS URL, allowing HTTP only for local development."""

        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("candidate base URL must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("candidate base URL cannot include a query or fragment")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and parsed.hostname not in local_hosts:
            raise ValueError("candidate base URL must use HTTPS outside local development")
        return normalized

    @model_validator(mode="after")
    def validate_expiry_policy(self) -> "InvitationSettings":
        """Ensure the default never silently exceeds the configured maximum."""

        if self.local_queue_enabled and self.delivery_provider == "resend":
            raise ValueError("local queue and Resend are separate delivery modes")
        if self.default_expiry_hours > self.maximum_expiry_hours:
            raise ValueError("default invite expiry cannot exceed maximum expiry")
        return self
