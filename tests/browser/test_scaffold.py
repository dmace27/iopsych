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
    from fixtures import JOB_DESCRIPTION, SyntheticExtraction

    from app.extraction.provider import RoleExtractionInput
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
    from fixtures import LocalMailboxDelivery

    from app.invitations.delivery import InvitationEmail

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
        socket.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
        with pytest.raises(OSError, match="occupied"):
            runner.preflight()


def test_synthetic_credentials_use_real_verifier_and_fixed_identities():
    from fixtures import synthetic_credentials

    from app.auth.tokens import HmacJwtVerifier, TokenValidationError
    from app.database.seed import ALPHA_ORGANIZATION_ID, BEACON_ORGANIZATION_ID

    environment = {
        "BROWSER_E2E_OWNED": "1",
        "AUTH_JWT_SECRET": "synthetic-test-key-" * 3,
        "AUTH_JWT_ISSUER": "https://auth.example.invalid",
        "AUTH_JWT_AUDIENCE": "iopsych-api",
    }
    verifier = HmacJwtVerifier(
        secret=environment["AUTH_JWT_SECRET"],
        issuer=environment["AUTH_JWT_ISSUER"],
        audience=environment["AUTH_JWT_AUDIENCE"],
        leeway_seconds=0,
    )
    credentials = synthetic_credentials(environment)
    assert (
        verifier.verify(credentials["BROWSER_E2E_RECRUITER"]).organization_id
        == ALPHA_ORGANIZATION_ID
    )
    assert (
        verifier.verify(credentials["BROWSER_E2E_MANAGER"]).organization_id
        == BEACON_ORGANIZATION_ID
    )
    with pytest.raises(TokenValidationError):
        verifier.verify(credentials["BROWSER_E2E_RECRUITER"] + "invalid")
    with pytest.raises(RuntimeError, match="isolated runner"):
        synthetic_credentials({})


def test_all_allocated_ports_are_checked_and_protected_ports_untouched(tmp_path):
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
        runner.preflight()
        ports = [
            call.args[0][1]
            for call in socket.return_value.__enter__.return_value.bind.call_args_list
        ]
        assert ports == [3116, 8116, 5556, 1136, 8136]
        assert not {3000, 8000, 8001}.intersection(ports)


def test_all_generated_credentials_are_removed_from_diagnostics():
    secrets = ["synthetic-invite", "synthetic-jwt", "synthetic-signing-key"]
    output = runner.redact(" ".join(secrets) + " safe test result", secrets)
    assert output == "[REDACTED] [REDACTED] [REDACTED] safe test result"


def test_fixture_application_cannot_start_without_owned_runner():
    from fixtures import create_fixture_app

    with (
        patch.dict(os.environ, {}, clear=True),
        pytest.raises(RuntimeError, match="isolated runner"),
    ):
        create_fixture_app()
