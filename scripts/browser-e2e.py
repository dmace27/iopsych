"""Own a fresh local production-build browser stack; never reuse/reset a database."""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "tests/browser"
DB = "postgresql+psycopg://iopsych_e2e:synthetic-local-only@127.0.0.1:5556/iopsych_e2e"
WEB = "http://127.0.0.1:3116"
API = "http://127.0.0.1:8116"
MAIL = "http://127.0.0.1:8136"


def preflight():
    # No inherited destination, proxy, credentials, or dotenv can redirect this run.
    protected = (
        "DATABASE_",
        "API_BASE_",
        "AUTH_",
        "INVITE_",
        "ROLE_EXTRACTION_",
        "SMTP_",
        "MAIL_",
        "BROWSER_E2E_",
        "NEXT_PUBLIC_",
        "DOCKER_",
        "COMPOSE_",
    )
    for key in os.environ:
        if key.startswith(protected) or key.lower() in {
            "http_proxy",
            "https_proxy",
            "all_proxy",
        }:
            raise RuntimeError(f"Unset inherited target/credential setting: {key}")
    endpoint = json.loads(subprocess.check_output(["docker", "context", "inspect"]))[0][
        "Endpoints"
    ]["docker"]["Host"]
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Docker must use a local Unix socket context")
    for directory in (ROOT, ROOT / "apps/api", ROOT / "apps/web"):
        if any(not path.name.endswith(".example") for path in directory.glob(".env*")):
            raise RuntimeError("Run in a checkout without local dotenv files")
    for port in (3116, 8116, 5556, 1136, 8136):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def ready(url, process=None):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Owned server exited during startup")
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Owned service failed its readiness deadline")


def redact(output, secrets_to_redact):
    """Redact every generated bearer credential before displaying diagnostics."""
    for secret in secrets_to_redact:
        output = output.replace(secret, "[REDACTED]")
    return output


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    preflight()
    environment = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT")
        if key in os.environ
    }
    environment.update(
        DATABASE_URL=DB,
        DATABASE_ECHO="false",
        API_BASE_URL=API,
        AUTH_JWT_SECRET=secrets.token_urlsafe(48),
        AUTH_JWT_ISSUER="https://auth.example.invalid",
        AUTH_JWT_AUDIENCE="iopsych-api",
        INVITE_TOKEN_SIGNING_SECRET=secrets.token_urlsafe(48),
        INVITE_CANDIDATE_BASE_URL=f"{WEB}/candidate/invites",
        ROLE_EXTRACTION_PROVIDER="disabled",
        ROLE_EXTRACTION_API_KEY="",
        ROLE_EXTRACTION_BASE_URL=f"{API}/disabled-provider",
        BROWSER_E2E_OWNED="1",
        NEXT_TELEMETRY_DISABLED="1",
        PYTHONPATH=f"{ROOT / 'apps/api'}{os.pathsep}{BROWSER}",
    )
    project = f"iopsych-e2e-{uuid4().hex[:12]}"
    compose = ["docker", "compose", "-p", project, "-f", str(BROWSER / "compose.yaml")]

    def run(args, **kwargs):
        subprocess.run(args, cwd=ROOT, env=environment, check=True, **kwargs)

    with ExitStack() as stack:
        # Cleanup only resources with this fresh project name, including failed startup.
        stack.callback(
            lambda: subprocess.run(
                [*compose, "down", "--volumes", "--remove-orphans"],
                cwd=ROOT,
                env=environment,
                check=True,
            )
        )
        run([*compose, "up", "-d", "--wait", "--wait-timeout", "60"])
        ready(f"{MAIL}/api/v1/messages")
        run(
            [
                str(ROOT / ".venv/bin/alembic"),
                "-c",
                "apps/api/alembic.ini",
                "upgrade",
                "head",
            ]
        )
        sys.path[:0] = [str(ROOT / "apps/api"), str(BROWSER)]
        from fixtures import LocalMailboxDelivery, seed_browser_admin, synthetic_credentials
        from sqlalchemy import create_engine

        from app.database.models import AssessmentInvite, AssessmentInviteStatus
        from app.database.seed import ALPHA_PROFILE_ID, seed_database
        from app.database.session import create_session_factory
        from app.invitations.delivery import build_invitation_email
        from app.invitations.tokens import InviteTokenCodec

        engine = create_engine(DB)
        stack.callback(engine.dispose)
        expires = datetime.now(UTC) + timedelta(hours=1)
        tokens = {}
        with create_session_factory(engine)() as session:
            seed_database(session)
            seed_browser_admin(session)
            for name in ("INVITE", "COMPLETE", "DENIED", "QUOTA"):
                token = InviteTokenCodec(environment["INVITE_TOKEN_SIGNING_SECRET"]).generate()
                tokens[f"BROWSER_E2E_{name}"] = token.raw_token
                session.add(
                    AssessmentInvite(
                        role_profile_id=ALPHA_PROFILE_ID,
                        email=f"{name.lower()}@example.invalid",
                        token_hash=token.token_hash,
                        expires_at=expires,
                        status=AssessmentInviteStatus.ACTIVE,
                    )
                )
            session.commit()
        for name, raw_token in tokens.items():
            LocalMailboxDelivery().send(
                build_invitation_email(
                    recipient_email=f"{name.removeprefix('BROWSER_E2E_').lower()}@example.invalid",
                    organization_name="Synthetic browser fixture",
                    invite_url=f"{WEB}/candidate/invites/{raw_token}",
                    expires_at=expires,
                    privacy_contact_email="privacy@example.invalid",
                )
            )
        with build_opener(ProxyHandler({})).open(f"{MAIL}/api/v1/messages") as response:
            assert json.load(response)["total"] == len(tokens), "Synthetic mailbox count mismatch"
        credentials = synthetic_credentials(environment)
        environment.update(tokens)
        environment.update(credentials)
        run(["npm", "run", "build"])
        log = stack.enter_context(tempfile.TemporaryFile())

        def launch(args):
            process = subprocess.Popen(
                args,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            stack.callback(stop, process)
            return process

        api = launch(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "fixtures:create_fixture_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8116",
                "--no-proxy-headers",
            ]
        )
        ready(f"{API}/health", api)
        web = launch(
            [
                "npm",
                "run",
                "start",
                "--workspace",
                "@iopsych/web",
                "--",
                "--hostname",
                "127.0.0.1",
                "--port",
                "3116",
            ]
        )
        ready(f"{WEB}/api/health", web)
        artifacts = stack.enter_context(
            tempfile.TemporaryDirectory(prefix="iopsych-e2e-artifacts-")
        )
        result = subprocess.run(
            ["npm", "--prefix", "tests/browser", "test", "--", "--output", artifacts],
            cwd=ROOT,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        print(
            redact(
                result.stdout,
                (
                    *tokens.values(),
                    *credentials.values(),
                    environment["AUTH_JWT_SECRET"],
                    environment["INVITE_TOKEN_SIGNING_SECRET"],
                ),
            )
        )
        result.check_returncode()
    print("PASS: expanded isolated browser coverage; full package 12A acceptance remains open")


if __name__ == "__main__":
    main()
