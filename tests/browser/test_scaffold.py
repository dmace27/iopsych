"""Focused safety tests: no service starts in these tests."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "tests/browser")]
spec = importlib.util.spec_from_file_location("runner", ROOT / "scripts/browser-e2e.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize(
    "key,value",
    [
        ("DATABASE_URL", "postgresql://external.invalid/real"),
        ("API_BASE_URL", "https://external.invalid"),
        ("INVITE_CANDIDATE_BASE_URL", "https://external.invalid"),
        ("SMTP_HOST", "external.invalid"),
        ("MAIL_URL", "https://external.invalid"),
        ("ROLE_EXTRACTION_BASE_URL", "https://external.invalid"),
        ("HTTPS_PROXY", "https://external.invalid"),
        ("DOCKER_HOST", "tcp://external.invalid:2375"),
    ],
)
def test_inherited_targets_fail_before_docker(key, value):
    with (
        patch.dict(os.environ, {key: value}, clear=True),
        patch.object(runner.subprocess, "check_output") as docker,
    ):
        with pytest.raises(RuntimeError, match="Unset inherited"):
            runner.preflight()
        docker.assert_not_called()


def test_remote_docker_context_rejected():
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(
            runner.subprocess,
            "check_output",
            return_value=b'[{"Endpoints":{"docker":{"Host":"ssh://remote"}}}]',
        ),
        pytest.raises(RuntimeError, match="local Unix socket"),
    ):
        runner.preflight()


def test_fixture_is_deterministic_and_schema_valid():
    from app.extraction.provider import RoleExtractionInput
    from fixtures import JOB_DESCRIPTION, SyntheticExtraction
    from iopsych_contracts import RoleExtraction

    role = RoleExtractionInput(
        title="Synthetic",
        department="Test",
        location="Local",
        job_description=JOB_DESCRIPTION,
    )
    result = SyntheticExtraction().extract(role)
    assert result == SyntheticExtraction().extract(role)
    assert RoleExtraction.model_validate(result).needs_human_review
    with pytest.raises(ValueError):
        SyntheticExtraction().extract(
            RoleExtractionInput(
                title="Other",
                department="Test",
                location="Local",
                job_description="unrecognized",
            )
        )


def test_mail_rejects_real_recipient_before_connecting():
    from app.invitations.delivery import InvitationEmail
    from fixtures import LocalMailboxDelivery

    with patch("smtplib.SMTP") as smtp:
        with pytest.raises(ValueError, match="synthetic"):
            LocalMailboxDelivery().send(
                InvitationEmail("person@example.com", "Test", "Test", "<p>Test</p>")
            )
        smtp.assert_not_called()


def test_local_dotenv_is_rejected(tmp_path):
    (tmp_path / ".env.local").write_text("DATABASE_URL=do-not-read")
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(runner, "ROOT", tmp_path),
        patch.object(
            runner.subprocess,
            "check_output",
            return_value=b'[{"Endpoints":{"docker":{"Host":"unix:///local.sock"}}}]',
        ),
        pytest.raises(RuntimeError, match="without local dotenv"),
    ):
        runner.preflight()


def test_occupied_port_is_not_reused(tmp_path):
    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(runner, "ROOT", tmp_path),
        patch.object(
            runner.subprocess,
            "check_output",
            return_value=b'[{"Endpoints":{"docker":{"Host":"unix:///local.sock"}}}]',
        ),
        patch.object(runner.socket, "socket") as socket,
    ):
        socket.return_value.__enter__.return_value.bind.side_effect = OSError(
            "occupied"
        )
        with pytest.raises(OSError, match="occupied"):
            runner.preflight()
