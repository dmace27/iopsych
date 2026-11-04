"""Explicitly injected, synthetic-only SMTP capture; never a production provider."""

from __future__ import annotations

import ipaddress
import math
import re
import smtplib
from contextlib import suppress
from dataclasses import dataclass
from email.message import EmailMessage

from app.invitations.delivery import InvitationDeliveryError, InvitationEmail

_SYNTHETIC_RECIPIENT = re.compile(
    r"[A-Za-z0-9_+.-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+(?:test|invalid)",
    re.ASCII | re.IGNORECASE,
)
_SENDER = "invitations@iopsych.invalid"


@dataclass(frozen=True, kw_only=True)
class LocalSmtpInvitationDelivery:
    """Capture synthetic mail in an operator-controlled, non-relaying local SMTP sink.

    Construction requires explicit opt-in. No environment discovery, authentication,
    retries, or runtime installation occurs here. Timeout bounds each socket operation,
    not the total duration of a malicious slow-drip SMTP conversation. The sink must
    have relay/forwarding disabled and its UI must remain private to the local operator.
    """

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 1139
    timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.enabled is not True:
            raise ValueError("local invitation capture requires explicit opt-in")
        # Reject names, URL syntax, scope identifiers and alternative IPv4 spellings.
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError:
            raise ValueError("local invitation capture requires numeric loopback") from None
        if (
            not address.is_loopback
            or "%" in self.host
            or (address.version == 6 and address != ipaddress.IPv6Address("::1"))
        ):
            raise ValueError("local invitation capture requires numeric loopback")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("local invitation capture port is invalid")
        if (
            isinstance(self.timeout_seconds, bool)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 10
        ):
            raise ValueError("local invitation capture timeout must be in (0, 10] seconds")

    def send(self, message: InvitationEmail) -> None:
        """Send one message; failures disclose no recipient, body, token or SMTP reply."""
        if not _SYNTHETIC_RECIPIENT.fullmatch(message.recipient_email):
            raise InvitationDeliveryError("local invitation capture requires synthetic recipient")
        client = None
        try:
            rendered = EmailMessage()
            rendered["From"] = _SENDER
            rendered["To"] = message.recipient_email
            rendered["Subject"] = message.subject
            rendered.set_content(message.text_body)
            rendered.add_alternative(message.html_body, subtype="html")
            # Explicit local_hostname avoids getfqdn() and hostname DNS discovery.
            client = smtplib.SMTP(timeout=self.timeout_seconds, local_hostname="[127.0.0.1]")
            client.connect(self.host, self.port)
            refused = client.send_message(
                rendered, from_addr=_SENDER, to_addrs=[message.recipient_email]
            )
            if not refused:
                return
        except (OSError, smtplib.SMTPException, ValueError, UnicodeError):
            pass
        finally:
            if client is not None:
                # DATA acceptance is success even if the peer disconnects on teardown.
                # close() sends no QUIT command and cannot expose a server response.
                with suppress(OSError):
                    client.close()
        # Raise outside the handler: even the exception context has no provider payload.
        raise InvitationDeliveryError("local invitation capture failed; acceptance may be unknown")
