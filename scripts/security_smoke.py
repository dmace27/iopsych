"""Exercise the production web/API security boundary using an isolated PG schema.

Run after ``npm run build`` with DATABASE_URL naming a disposable PostgreSQL
instance. The script creates only synthetic data, issues ephemeral credentials,
starts both servers on loopback, and removes its own schema/processes on exit.
No bearer credentials, response payloads, or raw server logs are printed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database.models import AssessmentInvite, AssessmentInviteStatus
from app.database.seed import (
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    BEACON_ROLE_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.invitations.tokens import InviteTokenCodec

ROOT = Path(__file__).resolve().parents[1]


def available_port() -> int:
    """Reserve a candidate loopback port for one of the short-lived test servers."""

    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def jwt(secret: str) -> str:
    """Generate a short-lived synthetic recruiter token with required claims."""

    def segment(value: object) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    header = segment({"alg": "HS256", "typ": "JWT"})
    claims = segment(
        {
            "iss": "https://auth.example.invalid",
            "aud": "iopsych-api",
            "sub": "synthetic-alpha-recruiter",
            "organization_id": "00000000-0000-4000-8000-000000000001",
            "exp": time.time() + 600,
        }
    )
    signature = hmac.new(secret.encode(), f"{header}.{claims}".encode(), hashlib.sha256).digest()
    return f"{header}.{claims}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def http(
    url: str,
    *,
    method: str = "GET",
    payload: object = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Read real HTTP responses, including expected 4xx responses, without logs."""

    request_headers = dict(headers or {})
    body = None if payload is None else json.dumps(payload).encode()
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return (
            response.status,
            {k.lower(): v for k, v in response.headers.items()},
            response.read(),
        )


def stop_server(process: subprocess.Popen[bytes]) -> None:
    """Stop the npm/Node or Uvicorn process group, including child processes."""

    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def wait_ready(url: str, process: subprocess.Popen[bytes]) -> None:
    """Wait with a deadline and fail if a server exits before becoming healthy."""

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("A smoke-test server exited during startup")
        try:
            if http(url)[0] == 200:
                return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.1)
    raise RuntimeError("A smoke-test server did not become healthy")


def verify(web: str, api: str, token: str, candidate: str) -> None:
    """Verify live session, consent, report, isolation, CSP, and throttle flows."""

    status, headers, html = http(f"{web}/sign-in")
    assert status == 200
    policy = headers["content-security-policy"]
    nonce = re.search(r"'nonce-([^']+)'", policy)
    assert nonce is not None and f'nonce="{nonce[1]}"'.encode() in html
    assert "'unsafe-eval'" not in policy and "'unsafe-inline'" not in policy.split("style-src")[0]
    assert http(f"{web}/sign-in")[1]["content-security-policy"] != policy
    for key, value in {
        "cache-control": "no-store",
        "referrer-policy": "no-referrer",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
    }.items():
        assert headers[key] == value
    assert headers["strict-transport-security"] == "max-age=31536000"

    assert http(f"{web}/api/internal/roles")[0] == 401
    assert (
        http(
            f"{web}/api/session",
            method="POST",
            payload={"token": token},
            headers={"Origin": "https://attacker.invalid"},
        )[0]
        == 403
    )
    status, session_headers, _ = http(
        f"{web}/api/session",
        method="POST",
        payload={"token": token},
        headers={"Origin": web},
    )
    assert status == 200
    cookie_header = session_headers["set-cookie"]
    assert cookie_header.startswith("__Host-iopsych_internal_token=")
    assert all(
        flag in cookie_header.lower()
        for flag in ("httponly", "secure", "samesite=strict", "max-age=28800")
    )
    # urllib is not a browser; explicitly send the returned Secure cookie for
    # loopback HTTP checks, while separately asserting its production flags.
    auth = {"Cookie": cookie_header.split(";")[0], "Origin": web}
    assert http(f"{web}/api/internal/roles", headers=auth)[0] == 200
    assert http(f"{web}/api/internal/roles/{BEACON_ROLE_ID}", headers=auth)[0] == 404
    assert (
        http(
            f"{web}/api/internal/roles/{ALPHA_ROLE_ID}",
            method="PATCH",
            payload={},
            headers={**auth, "Origin": "https://attacker.invalid"},
        )[0]
        == 403
    )

    candidate_url = f"{web}/api/candidate/invites/{candidate}"
    status, _, notice = http(candidate_url)
    assert status == 200 and not json.loads(notice)["can_start_assessment"]
    definition = json.loads(
        (ROOT / "packages/shared/definitions/v1/pilot-assessment.json").read_text()
    )
    answers = {
        "assessment_definition_id": definition["id"],
        "assessment_definition_version": definition["version"],
        "responses": [
            {
                "block_id": block["id"],
                "skipped": False,
                "most_like_item_id": block["items"][0]["id"],
                "least_like_item_id": block["items"][1]["id"],
            }
            for block in definition["blocks"]
        ],
    }
    assert (
        http(
            f"{candidate_url}/submit",
            method="POST",
            payload=answers,
            headers={"Origin": web},
        )[0]
        == 409
    )
    assert (
        http(
            f"{candidate_url}/consent",
            method="POST",
            payload={"decision": "consent"},
            headers={"Origin": web},
        )[0]
        == 200
    )
    status, _, receipt = http(
        f"{candidate_url}/submit",
        method="POST",
        payload=answers,
        headers={"Origin": web},
    )
    assert status == 201 and set(json.loads(receipt)) == {"assessment_id"}
    status, report_headers, report = http(
        f"{web}/api/internal/reports",
        method="POST",
        payload={
            "assessment_id": json.loads(receipt)["assessment_id"],
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
        headers=auth,
    )
    assert status == 201 and report_headers["cache-control"] == "no-store"
    report_payload = json.loads(report)
    assert len(report_payload["result"]["items"]) == 6
    assert report_payload["result"]["role_profile_approved"] is True
    assert http(f"{web}/api/internal/reports/{report_payload['id']}", headers=auth)[0] == 200
    assert http(f"{web}/api/session", method="DELETE", headers=auth)[0] == 204
    assert http(f"{web}/api/internal/roles")[0] == 401

    # Exhaust the real shared API peer budget and verify both BFFs preserve 429
    # and Retry-After, rather than turning the response into an auth failure.
    for _ in range(301):
        if http(f"{api}/v1/auth/me")[0] == 429:
            break
    else:
        raise AssertionError("API peer rate limit was not enforced")
    for url, method, payload, caller_headers in (
        (f"{web}/api/session", "POST", {"token": token}, {"Origin": web}),
        (f"{web}/api/internal/roles", "GET", None, auth),
        (candidate_url, "GET", None, {}),
    ):
        status, limited_headers, _ = http(
            url, method=method, payload=payload, headers=caller_headers
        )
        assert status == 429 and int(limited_headers["retry-after"]) > 0
        assert limited_headers["cache-control"] == "no-store"


def main() -> None:
    """Own and clean up an isolated schema and both production test processes."""

    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql":
        raise ValueError("Security smoke verification requires PostgreSQL")
    engine = create_engine(url)
    schema = f"security_smoke_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"})
        environment = dict(
            os.environ, DATABASE_URL=isolated_url.render_as_string(hide_password=False)
        )
        environment.update(
            AUTH_JWT_SECRET=secrets.token_urlsafe(48),
            INVITE_TOKEN_SIGNING_SECRET=secrets.token_urlsafe(48),
        )
        subprocess.run(
            [str(ROOT / ".venv/bin/alembic"), "upgrade", "head"],
            cwd=ROOT / "apps/api",
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        fixture_engine = create_engine(isolated_url)
        factory = create_session_factory(fixture_engine)
        generated = InviteTokenCodec(environment["INVITE_TOKEN_SIGNING_SECRET"]).generate()
        with factory() as session:
            seed_database(session)
            session.add(
                AssessmentInvite(
                    role_profile_id=ALPHA_PROFILE_ID,
                    email="smoke@example.invalid",
                    token_hash=generated.token_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    status=AssessmentInviteStatus.ACTIVE,
                )
            )
            session.commit()
        fixture_engine.dispose()
        api = f"http://127.0.0.1:{available_port()}"
        web = f"http://127.0.0.1:{available_port()}"
        environment["API_BASE_URL"] = api
        with ExitStack() as stack:
            log = stack.enter_context(tempfile.TemporaryFile())
            api_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--app-dir",
                    "apps/api",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    api.rsplit(":", 1)[1],
                    "--no-proxy-headers",
                ],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            stack.callback(stop_server, api_process)
            web_process = subprocess.Popen(
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
                    web.rsplit(":", 1)[1],
                ],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            stack.callback(stop_server, web_process)
            wait_ready(f"{api}/health", api_process)
            wait_ready(f"{web}/api/health", web_process)
            internal_token = jwt(environment["AUTH_JWT_SECRET"])
            verify(web, api, internal_token, generated.raw_token)
            stop_server(web_process)
            stop_server(api_process)
            log.seek(0)
            server_output = log.read().decode()
            assert "--- Logging error ---" not in server_output
            assert "GET /v1/auth/me HTTP/1.1" in server_output
            assert generated.raw_token not in server_output
            assert internal_token not in server_output
            assert environment["AUTH_JWT_SECRET"] not in server_output
            assert environment["INVITE_TOKEN_SIGNING_SECRET"] not in server_output
        print(
            "PASS: production CSP, session/CSRF, tenant isolation, consent/submission, "
            "report, logout, and BFF rate-limit flows"
        )
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


if __name__ == "__main__":
    main()
