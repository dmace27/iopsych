"""Narrow invitation-email boundary that cannot accept assessment data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Protocol


class InvitationDeliveryError(RuntimeError):
    """A safe provider-agnostic delivery failure."""


@dataclass(frozen=True)
class InvitationEmail:
    """Fully rendered transactional email with no assessment payload fields."""

    recipient_email: str
    subject: str
    text_body: str
    html_body: str


class InvitationDeliveryAdapter(Protocol):
    """Send one already-rendered invitation through a transactional provider."""

    def send(self, message: InvitationEmail) -> None:
        """Deliver the email or raise ``InvitationDeliveryError``."""


class UnconfiguredInvitationDelivery:
    """Fail closed without printing or otherwise leaking candidate links."""

    def send(self, message: InvitationEmail) -> None:
        """Reject delivery until an explicit provider adapter is installed."""

        del message
        raise InvitationDeliveryError("invitation delivery is not configured")


def build_invitation_email(
    *,
    recipient_email: str,
    organization_name: str,
    invite_url: str,
    expires_at: datetime,
    privacy_contact_email: str,
) -> InvitationEmail:
    """Render the minimal-purpose email; answers, items, and scores are impossible inputs."""

    subject = f"Invitation from {organization_name}"
    expiry = expires_at.isoformat()
    text_body = (
        f"{organization_name} invited you to a work-preference questionnaire.\n\n"
        "Review the purpose, data use, and consent information before deciding whether "
        "to participate. Declining carries no penalty.\n\n"
        f"Open your secure invitation: {invite_url}\n\n"
        f"This link expires at {expiry}. For privacy questions, contact "
        f"{privacy_contact_email}."
    )
    html_body = (
        f"<p>{escape(organization_name)} invited you to a work-preference "
        "questionnaire.</p>"
        "<p>Review the purpose, data use, and consent information before deciding "
        "whether to participate. Declining carries no penalty.</p>"
        f'<p><a href="{escape(invite_url, quote=True)}">Open your secure invitation</a></p>'
        f"<p>This link expires at {escape(expiry)}. For privacy questions, contact "
        f"{escape(privacy_contact_email)}.</p>"
    )
    return InvitationEmail(
        recipient_email=recipient_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
