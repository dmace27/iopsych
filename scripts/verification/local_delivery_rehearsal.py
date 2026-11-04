#!/usr/bin/env python3
"""Explicit synthetic API → PostgreSQL queue → Mailpit rehearsal; not a scheduler."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "iopsych-delivery-rehearsal"
DATABASE = "iopsych_delivery_rehearsal"
PORTS = (5599, 1140, 8140)
POSTGRES = "postgres:16-bookworm"
MAILPIT = "axllent/mailpit:v1.27.10"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def guard(project, environment, root=ROOT):
    require(project == PROJECT, "explicit own-project opt-in required")
    forbidden = {"DATABASE_URL", "DOCKER_HOST", "DOCKER_CONTEXT", "DATABASE_ECHO"}
    require(
        not any(
            key in forbidden
            or key.startswith(
                ("PG", "TEST_", "AUTH_", "INVITE_", "ROLE_EXTRACTION_", "OPENAI_")
            )
            for key in environment
        ),
        "unset ambient database, Docker, test and provider configuration",
    )
    require(
        not any((root / name).exists() for name in (".env", "apps/api/.env")),
        "repository and API .env must be absent",
    )


def local_endpoint(endpoint):
    require(
        bool(re.fullmatch(r"unix:///[^\s?#]+", endpoint)),
        "Docker must use an absolute local Unix socket",
    )
    return endpoint


def run(*args):
    return (
        subprocess.run(args, capture_output=True, check=True, timeout=30)
        .stdout.decode()
        .strip()
    )


def owned_cleanup(docker, kind, identifier, owner):
    label = run(
        *docker,
        kind,
        "inspect",
        "--format",
        '{{index .Labels "rehearsal.owner"}}'
        if kind == "network"
        else '{{index .Config.Labels "rehearsal.owner"}}',
        identifier,
    )
    require(label == owner, "refusing cleanup of non-owned resource")
    if kind == "network":
        run(*docker, "network", "rm", identifier)
    else:
        run(*docker, "rm", "--force", "--volumes", identifier)


def exercise(url):
    # Imports occur only after guard checks and creation of our own database.
    from datetime import UTC, datetime, timedelta

    import httpx
    from alembic import command
    from alembic.config import Config
    from app.auth.config import AuthenticationSettings
    from app.database.models import AuditEvent, InvitationDelivery
    from app.database.seed import (
        ALPHA_ORGANIZATION_ID,
        ALPHA_PROFILE_ID,
        ALPHA_ROLE_ID,
        seed_database,
    )
    from app.database.session import create_session_factory
    from app.invitations.config import InvitationSettings
    from app.invitations.local_delivery import LocalSmtpInvitationDelivery
    from app.invitations.worker import LocalDeliveryWorker, cleanup_deliveries
    from app.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event, func, select
    from sqlalchemy.exc import SQLAlchemyError

    config = Config(str(ROOT / "apps/api/alembic.ini"))
    command.upgrade(config, "head")
    # Alembic reconfigures logging; disable again before handling bearer URLs.
    logging.disable(logging.CRITICAL)
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=10000 -c lock_timeout=3000",
        },
    )
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            seed_database(session)
            session.commit()
        secret = secrets.token_hex(32)
        authentication = AuthenticationSettings(
            _env_file=None, environment="development", jwt_secret=secret
        )
        settings = InvitationSettings(
            _env_file=None,
            local_queue_enabled=True,
            allow_synthetic_definitions=True,
            local_queue_key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            token_signing_secret=secrets.token_hex(32),
            candidate_base_url="http://127.0.0.1/candidate/invites",
        )
        adapter = LocalSmtpInvitationDelivery(enabled=True, port=1140)
        worker = LocalDeliveryWorker(factory, settings, authentication, adapter)
        app = create_app(
            authentication_settings=authentication,
            invitation_settings=settings,
            invitation_delivery=adapter,
            session_factory=factory,
        )

        def encode(value):
            return (
                base64.urlsafe_b64encode(json.dumps(value).encode())
                .decode()
                .rstrip("=")
            )

        now = int(time.time())
        signing = (
            encode({"alg": "HS256", "typ": "JWT"})
            + "."
            + encode(
                {
                    "sub": "synthetic-alpha-recruiter",
                    "organization_id": str(ALPHA_ORGANIZATION_ID),
                    "iss": authentication.jwt_issuer,
                    "aud": authentication.jwt_audience,
                    "iat": now,
                    "nbf": now,
                    "exp": now + 300,
                }
            )
        )
        signature = (
            base64.urlsafe_b64encode(
                hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )
        headers = {"Authorization": f"Bearer {signing}.{signature}"}

        def terminal(identifier, state):
            with factory() as session:
                job = session.scalar(
                    select(InvitationDelivery).where(
                        InvitationDelivery.invite_id == identifier
                    )
                )
                require(
                    job is not None
                    and job.state.value == state
                    and job.attempt_count == 1,
                    "terminal state or attempt count mismatch",
                )
                require(
                    job.credential_ciphertext is None and job.credential_key_id is None,
                    "terminal credential was retained",
                )
                audits = session.scalars(
                    select(AuditEvent).where(AuditEvent.entity_id == identifier)
                ).all()
                types = {row.event_type for row in audits}
                require(
                    {
                        "assessment_invite.created",
                        "invitation_delivery.queued",
                        "invitation_delivery.sending",
                        f"invitation_delivery.{state}",
                    }
                    <= types,
                    "required audit evidence absent",
                )
                for row in audits:
                    if row.event_type.startswith("invitation_delivery."):
                        require(
                            set(row.metadata_json) <= {"mode", "attempt_count"},
                            "unexpected delivery audit metadata",
                        )

        with (
            TestClient(app) as api,
            httpx.Client(
                base_url="http://127.0.0.1:8140", trust_env=False, timeout=3
            ) as mail,
        ):

            def captured():
                response = mail.get("/api/v1/messages")
                require(response.status_code == 200, "Mailpit listing failed")
                return response.json()

            def issue(label):
                response = api.post(
                    f"/v1/roles/{ALPHA_ROLE_ID}/invites",
                    headers={
                        **headers,
                        "Idempotency-Key": f"synthetic-rehearsal-{label}",
                    },
                    json={
                        "role_profile_id": str(ALPHA_PROFILE_ID),
                        "email": f"{label}@example.invalid",
                    },
                )
                require(response.status_code == 201, "API issuance failed")
                return UUID(response.json()["id"])

            require(captured()["total"] == 0, "fresh capture was not empty")
            identifier = issue("success")
            require(
                issue("success") == identifier, "duplicate issuance changed invitation"
            )
            with factory() as session:
                require(
                    session.scalar(select(func.count()).select_from(InvitationDelivery))
                    == 1,
                    "duplicate issuance created another delivery",
                )
            require(captured()["total"] == 0, "issuance sent before worker drain")
            require(
                worker.drain(limit=2) == 1 and worker.drain(limit=2) == 0,
                "bounded drain/replay mismatch",
            )
            messages = captured()
            require(messages["total"] == 1, "expected exactly one captured email")
            response = mail.get(f"/api/v1/message/{messages['messages'][0]['ID']}")
            require(response.status_code == 200, "Mailpit message read failed")
            message = response.json()
            require(
                message["To"][0]["Address"] == "success@example.invalid",
                "capture recipient mismatch",
            )
            match = re.search(
                r"http://127\.0\.0\.1/candidate/invites/([^\s<>]+)", message["Text"]
            )
            require(match is not None, "capture lacks consent URL")
            token = match[1]
            landing = api.get(f"/v1/candidate/invites/{token}")
            require(
                landing.status_code == 200
                and landing.json()["invitation_id"] == str(identifier)
                and bool(landing.json()["consent_notice"]),
                "captured consent URL did not resolve",
            )
            with factory() as session:
                require(
                    token
                    not in json.dumps(
                        session.scalars(select(AuditEvent.metadata_json)).all()
                    ),
                    "bearer token leaked to audit",
                )
            del token, match, message, response, landing
            terminal(identifier, "sent")
            print(
                "PASS: authenticated POST, duplicate idempotency, bounded drain, actual Mailpit, consent resolution, cleared credential and audit"
            )

            uncertain = issue("uncertain")

            def fail_completion(session):
                if any(
                    isinstance(row, InvitationDelivery) and row.state.value == "sent"
                    for row in session.identity_map.values()
                ):
                    raise SQLAlchemyError("synthetic completion failure")

            event.listen(factory, "before_commit", fail_completion)
            try:
                try:
                    worker.drain(limit=1)
                except SQLAlchemyError:
                    pass
                else:
                    raise RuntimeError("completion fault was not exercised")
            finally:
                event.remove(factory, "before_commit", fail_completion)
            require(
                captured()["total"] == 2, "acceptance-before-commit evidence missing"
            )
            require(
                cleanup_deliveries(
                    factory, limit=2, now=datetime.now(UTC) + timedelta(minutes=3)
                )
                == 1,
                "stale recovery did not resolve one delivery",
            )
            terminal(uncertain, "uncertain")
            require(
                worker.drain(limit=2) == 0 and captured()["total"] == 2,
                "uncertain recovery resent email",
            )
            replay = api.post(
                f"/v1/roles/{ALPHA_ROLE_ID}/invites",
                headers={**headers, "Idempotency-Key": "synthetic-rehearsal-uncertain"},
                json={
                    "role_profile_id": str(ALPHA_PROFILE_ID),
                    "email": "uncertain@example.invalid",
                },
            )
            require(
                replay.status_code == 409,
                "uncertain replay did not require explicit reissue",
            )
            print(
                "PASS: actual SMTP acceptance followed by injected completion rollback; stale recovery clears credential, audits uncertainty, rejects replay and never resends"
            )
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help=f"required explicit opt-in: {PROJECT}")
    args = parser.parse_args()
    guard(args.project, os.environ)
    endpoint = local_endpoint(
        run(
            "docker",
            "context",
            "inspect",
            "desktop-linux",
            "--format",
            "{{.Endpoints.docker.Host}}",
        )
    )
    docker = ["docker", "--host", endpoint]
    for image in (POSTGRES, MAILPIT):
        run(*docker, "image", "inspect", image)  # Never pull, build or install.
    for port in PORTS:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    owner = f"{PROJECT}-{uuid4().hex}"
    network = None
    containers = []
    sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/shared/python")]
    logging.disable(logging.CRITICAL)
    try:
        network = run(
            *docker,
            "network",
            "create",
            "--opt",
            "com.docker.network.bridge.enable_ip_masquerade=false",
            "--label",
            f"rehearsal.owner={owner}",
            owner,
        )

        def start(suffix, image, *options):
            name = f"{owner}-{suffix}"
            # Record the unique name before launch so a timed-out start is cleanable.
            containers.append(name)
            run(
                *docker,
                "run",
                "--detach",
                "--pull=never",
                "--log-driver=none",
                "--name",
                name,
                "--label",
                f"rehearsal.owner={owner}",
                "--network",
                network,
                *options,
                image,
            )
            return name

        pg = start(
            "postgres",
            POSTGRES,
            "--publish",
            "127.0.0.1:5599:5432",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
            "--env",
            "POSTGRES_USER=rehearsal",
            "--env",
            f"POSTGRES_DB={DATABASE}",
            "--env",
            "POSTGRES_PASSWORD=synthetic-local-only",
        )
        start(
            "mailpit",
            MAILPIT,
            "--publish",
            "127.0.0.1:1140:1025",
            "--publish",
            "127.0.0.1:8140:8025",
            "--read-only",
            "--tmpfs",
            "/data:rw,noexec,nosuid,size=64m",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--env",
            "MP_DATABASE=/data/mailpit.db",
            "--env",
            "MP_MAX_MESSAGES=10",
        )
        for _ in range(60):
            try:
                run(
                    *docker, "exec", pg, "pg_isready", "-U", "rehearsal", "-d", DATABASE
                )
                with socket.create_connection(("127.0.0.1", 8140), timeout=1):
                    pass
                break
            except (subprocess.CalledProcessError, OSError):
                time.sleep(0.5)
        else:
            raise RuntimeError("owned services readiness timed out")
        url = f"postgresql+psycopg://rehearsal:synthetic-local-only@127.0.0.1:5599/{DATABASE}"
        os.environ["DATABASE_URL"] = url
        exercise(url)
    finally:
        os.environ.pop("DATABASE_URL", None)
        failures = []
        for name in reversed(containers):
            try:
                owned_cleanup(docker, "container", name, owner)
            except (RuntimeError, OSError, subprocess.SubprocessError):
                failures.append(name)
        if network is not None:
            try:
                owned_cleanup(docker, "network", network, owner)
            except (RuntimeError, OSError, subprocess.SubprocessError):
                failures.append(network)
        require(
            not failures,
            "owned resource cleanup incomplete; inspect rehearsal labels locally",
        )
        print(
            "Cleanup: removed only this run's owned containers, tmpfs data and private bridge"
        )


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - suppress credential-bearing exceptions
        # Never render exceptions/tracebacks containing credentials, requests or bodies.
        print(
            "FAIL: local delivery rehearsal failed; sensitive diagnostics suppressed",
            file=sys.stderr,
        )
        sys.exit(1)
