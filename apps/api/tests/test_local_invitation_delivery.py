"""Focused local capture boundary and opt-in Mailpit integration checks."""

from __future__ import annotations

import os
import smtplib
import traceback
from dataclasses import replace
from unittest.mock import patch

import httpx
import pytest

from app.invitations.delivery import (
    InvitationDeliveryAdapter,
    InvitationDeliveryError,
    InvitationEmail,
)
from app.invitations.local_delivery import LocalSmtpInvitationDelivery

MESSAGE = InvitationEmail(
    recipient_email="synthetic-candidate@example.test",
    subject="Synthetic invitation",
    text_body="Synthetic capture body",
    html_body="<p>Synthetic capture body</p>",
)


@pytest.mark.parametrize("enabled", [False, None, 1, "true"])
def test_explicit_opt_in(enabled: object) -> None:
    with pytest.raises(ValueError, match="opt-in"):
        LocalSmtpInvitationDelivery(enabled=enabled)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "mailpit",
        "example.test",
        "192.0.2.1",
        "0.0.0.0",
        "::",
        "::ffff:127.0.0.1",
        "127.1",
        "2130706433",
        "127.0.0.1:1139",
        "::1%lo0",
        " 127.0.0.1",
        "127.0.0.1\n",
    ],
)
def test_reject_non_numeric_or_non_loopback_hosts(host: str) -> None:
    with patch("socket.getaddrinfo") as dns, pytest.raises(ValueError, match="numeric loopback"):
        LocalSmtpInvitationDelivery(enabled=True, host=host)
    dns.assert_not_called()


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1"])
def test_loopback_literals(host: str) -> None:
    assert LocalSmtpInvitationDelivery(enabled=True, host=host).host == host


@pytest.mark.parametrize("port", [0, 65536, True, 1.5])
def test_invalid_port(port: int) -> None:
    with pytest.raises(ValueError, match="port"):
        LocalSmtpInvitationDelivery(enabled=True, port=port)


@pytest.mark.parametrize("timeout", [0, -1, 10.01, float("inf"), float("nan"), True])
def test_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        LocalSmtpInvitationDelivery(enabled=True, timeout_seconds=timeout)


@pytest.mark.parametrize(
    "recipient",
    [
        "person@gmail.com",
        "person@example.com",
        "a@example.test.evil.com",
        "a@example.test\n",
        "a@example.test,b@example.test",
        "Name <a@example.test>",
        "a@localhost",
    ],
)
def test_refuse_real_or_malformed_recipients(recipient: str) -> None:
    with patch("smtplib.SMTP") as smtp, pytest.raises(InvitationDeliveryError):
        LocalSmtpInvitationDelivery(enabled=True).send(replace(MESSAGE, recipient_email=recipient))
    smtp.assert_not_called()


def test_rendering_envelope_timeout_and_no_credentials() -> None:
    with patch("smtplib.SMTP") as smtp:
        client = smtp.return_value
        client.send_message.return_value = {}
        adapter: InvitationDeliveryAdapter = LocalSmtpInvitationDelivery(enabled=True)
        adapter.send(MESSAGE)
    smtp.assert_called_once_with(timeout=3.0, local_hostname="[127.0.0.1]")
    client.connect.assert_called_once_with("127.0.0.1", 1139)
    rendered = client.send_message.call_args.args[0]
    assert rendered["To"] == MESSAGE.recipient_email
    assert rendered["Subject"] == MESSAGE.subject
    assert rendered.get_body(preferencelist=("plain",)).get_content().strip() == MESSAGE.text_body
    assert rendered.get_body(preferencelist=("html",)).get_content().strip() == MESSAGE.html_body
    assert client.send_message.call_args.kwargs == {
        "from_addr": "invitations@iopsych.invalid",
        "to_addrs": [MESSAGE.recipient_email],
    }
    client.login.assert_not_called()
    client.set_debuglevel.assert_not_called()
    client.quit.assert_not_called()
    client.close.assert_called_once()


@pytest.mark.parametrize("stage", ["connect", "send_message"])
@pytest.mark.parametrize("failure", [TimeoutError, OSError, smtplib.SMTPException])
def test_safe_failures(
    stage: str, failure: type[Exception], caplog: pytest.LogCaptureFixture
) -> None:
    secret = "synthetic-sensitive-marker"
    with patch("smtplib.SMTP") as smtp:
        getattr(smtp.return_value, stage).side_effect = failure(secret)
        with pytest.raises(InvitationDeliveryError) as error:
            LocalSmtpInvitationDelivery(enabled=True).send(MESSAGE)
        smtp.return_value.close.assert_called_once()
    assert secret not in "".join(traceback.format_exception(error.value)) + caplog.text
    assert error.value.__context__ is None


def test_refused_recipient_response_is_sanitized() -> None:
    with patch("smtplib.SMTP") as smtp, pytest.raises(InvitationDeliveryError) as error:
        smtp.return_value.send_message.return_value = {"sensitive": (550, b"sensitive")}
        LocalSmtpInvitationDelivery(enabled=True).send(MESSAGE)
    assert "sensitive" not in str(error.value)


def test_header_injection_rejected_before_connect() -> None:
    with patch("smtplib.SMTP") as smtp, pytest.raises(InvitationDeliveryError):
        LocalSmtpInvitationDelivery(enabled=True).send(replace(MESSAGE, subject="x\nBcc: x@test"))
    smtp.assert_not_called()


@pytest.mark.skipif(os.environ.get("IOPSYCH_TEST_LOCAL_MAILPIT") != "1", reason="opt-in local sink")
def test_real_mailpit_capture() -> None:
    # Fixed isolated allocation; never accept a caller-supplied remote endpoint.
    with httpx.Client(base_url="http://127.0.0.1:8139", trust_env=False, timeout=3) as http:
        before = http.get("/api/v1/messages").raise_for_status().json()["total"]
        LocalSmtpInvitationDelivery(enabled=True).send(MESSAGE)
        captured = http.get("/api/v1/messages").raise_for_status().json()
        assert captured["total"] == before + 1
        message = (
            http.get(f"/api/v1/message/{captured['messages'][0]['ID']}").raise_for_status().json()
        )
        assert message["To"][0]["Address"] == MESSAGE.recipient_email
        assert message["Subject"] == MESSAGE.subject
        assert message["Text"].strip() == MESSAGE.text_body
        assert message["HTML"].strip() == MESSAGE.html_body


def test_close_failure_does_not_undo_acceptance() -> None:
    with patch("smtplib.SMTP") as smtp:
        smtp.return_value.send_message.return_value = {}
        smtp.return_value.close.side_effect = OSError("sensitive")
        LocalSmtpInvitationDelivery(enabled=True).send(MESSAGE)
