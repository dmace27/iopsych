"""Synthetic adapters, loaded only by the explicitly owned browser runner."""

import os
import smtplib
from email.message import EmailMessage

from app.extraction.provider import RoleExtractionInput
from app.invitations.delivery import InvitationEmail
from iopsych_contracts import CONSTRUCT_DEFINITIONS

JOB_DESCRIPTION = (
    "Synthetic work involves planning, shared learning, and changing priorities."
)


class SyntheticExtraction:
    """Deterministic fixture: deliberately rejects unrecognized source text."""

    def extract(self, role: RoleExtractionInput) -> object:
        if role.job_description != JOB_DESCRIPTION:
            raise ValueError("Use the explicit synthetic job description fixture")
        return {
            "constructs": [
                {
                    "key": definition.key.value,
                    "rating": 3,
                    "confidence": "medium",
                    "rationale": "Synthetic fixture for plumbing verification only.",
                    "evidence": [JOB_DESCRIPTION],
                }
                for definition in CONSTRUCT_DEFINITIONS
            ],
            "assumptions": [
                "Synthetic fixture; no scientific or human approval implied."
            ],
            "needs_human_review": True,
        }


class LocalMailboxDelivery:
    """No forwarding or arbitrary SMTP target; only reserved synthetic recipients."""

    def send(self, message: InvitationEmail) -> None:
        if not message.recipient_email.endswith("@example.invalid"):
            raise ValueError("Only synthetic example.invalid recipients are allowed")
        mail = EmailMessage()
        mail["From"] = "browser-runner@example.invalid"
        mail["To"] = message.recipient_email
        mail["Subject"] = message.subject
        mail.set_content(message.text_body)
        mail.add_alternative(message.html_body, subtype="html")
        with smtplib.SMTP("127.0.0.1", 1124, timeout=5) as smtp:
            smtp.send_message(mail)


def create_fixture_app():
    """Use existing factory seams, never patch the production module app."""
    if os.environ.get("BROWSER_E2E_OWNED") != "1":
        raise RuntimeError("Fixture app requires the isolated runner")
    from app.main import create_app

    return create_app(
        role_extraction_provider=SyntheticExtraction(),
        invitation_delivery=LocalMailboxDelivery(),
    )
