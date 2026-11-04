"""Resend HTTPS adapter with bounded requests and safe error classification."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from pydantic import SecretStr

from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryError,
    InvitationEmail,
    ProviderInvitationDeliveryAdapter,
    UnconfiguredInvitationDelivery,
)


class ResendInvitationDelivery:
    """Send only invitation fields; the worker supplies a stable idempotency key."""

    def __init__(self, api_key: SecretStr, *, timeout: float) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def send(self, message: InvitationEmail, *, idempotency_key: str) -> str:
        """Never expose provider bodies, message text, recipient or API keys in errors."""
        request = Request(
            "https://api.resend.com/emails",
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            data=json.dumps(
                {
                    "from": message.sender_email,
                    "to": [message.recipient_email],
                    "subject": message.subject,
                    "text": message.text_body,
                    "html": message.html_body,
                    "tags": [{"name": "delivery_id", "value": idempotency_key.split("/")[-1]}],
                }
            ).encode(),
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read(16_384))
            return str(UUID(payload["id"]))
        except HTTPError as exc:
            # Concurrent idempotent requests (409) are safe to retry. A payload
            # conflict also returns 409; retrying the frozen payload cannot send
            # a second email, and the bounded retry window eventually stops it.
            permanent = 400 <= exc.code < 500 and exc.code not in {408, 409, 429}
            raise InvitationDeliveryError(permanent=permanent) from None
        except (URLError, OSError, ValueError, KeyError, TypeError):
            # Includes timeouts after acceptance and malformed success bodies.
            raise InvitationDeliveryError() from None


def build_invitation_delivery(settings: InvitationSettings) -> ProviderInvitationDeliveryAdapter:
    """Configure the production adapter without allowing a credential-bearing custom URL."""
    if settings.delivery_provider == "resend" and settings.delivery_api_key is not None:
        return ResendInvitationDelivery(
            settings.delivery_api_key, timeout=settings.delivery_timeout_seconds
        )
    return UnconfiguredInvitationDelivery()
