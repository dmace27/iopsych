"""Regression checks for hardening before protected endpoint execution."""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.invitations.logging import CandidateInviteTokenFilter
from app.security import SecurityMiddleware


def test_security_headers_and_throttling() -> None:
    """Invalid-auth floods receive safe, non-cacheable failures and retry hints."""

    app = FastAPI()
    app.add_middleware(SecurityMiddleware, limit=1)
    with TestClient(app) as client:
        first = client.get("/v1/missing")
        assert first.status_code == 404
        assert first.headers["cache-control"] == "no-store"
        assert first.headers["x-content-type-options"] == "nosniff"
        assert first.headers["x-frame-options"] == "DENY"
        assert first.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in first.headers["content-security-policy"]
        second = client.get("/v1/another", headers={"X-Forwarded-For": "different"})
        assert second.status_code == 429
        assert int(second.headers["retry-after"]) > 0
        assert client.get("/health").status_code == 404


async def _ok(request: Request) -> Response:
    return Response(status_code=204)


def test_no_peer() -> None:
    """ASGI requests without a peer share a conservative fallback budget."""

    middleware = SecurityMiddleware(FastAPI())
    request = Request({"type": "http", "path": "/v1/test", "headers": []})
    assert (asyncio.run(middleware.dispatch(request, _ok))).status_code == 204


def test_browser_and_authorization_log_redaction() -> None:
    """Redact both web path forms and bearer headers without destroying context."""

    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        "",
        0,
        "GET /api/candidate/invites/secret/submit Bearer jwt",
        (),
        None,
    )
    CandidateInviteTokenFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "jwt" not in record.getMessage()
    assert "/submit" in record.getMessage()


def test_limiter_is_bounded_and_preserves_each_window() -> None:
    """Unique keys cannot grow memory indefinitely or evict an active budget."""

    import pytest

    from app.invitations.rate_limit import InMemoryRateLimiter

    now = [0.0]
    limiter = InMemoryRateLimiter(lambda: now[0], maximum_keys=2)
    assert limiter.check("long", limit=1, window_seconds=60).allowed
    assert limiter.check("short", limit=1, window_seconds=10).allowed
    assert not limiter.check("third", limit=1, window_seconds=10).allowed
    now[0] = 10.0
    assert limiter.check("third", limit=1, window_seconds=10).allowed
    assert not limiter.check("long", limit=1, window_seconds=10).allowed
    with pytest.raises(ValueError, match="maximum_keys"):
        InMemoryRateLimiter(maximum_keys=0)


def test_descendant_logger_and_exception_redaction() -> None:
    """Records bypassing parent logger filters remain safe at arbitrary handlers."""

    import io

    from app.invitations.logging import install_invite_token_log_filter

    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger("httpcore.future.child")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    install_invite_token_log_filter()
    try:
        logger.info("Authorization: Bearer %s, email %s", "sensitive-jwt", "person@example.invalid")
        try:
            raise ValueError("/candidate/invites/raw-credential/consent")
        except ValueError:
            logger.exception("request failed")
        record = logger.makeRecord(
            logger.name,
            logging.INFO,
            __file__,
            1,
            'token="sensitive-token"',
            (),
            None,
            sinfo="Bearer sensitive-stack",
        )
        handler.handle(record)
    finally:
        logger.removeHandler(handler)
    assert "sensitive" not in output.getvalue()
    assert "raw-credential" not in output.getvalue()
    assert "person@example.invalid" not in output.getvalue()
    assert "ValueError" in output.getvalue()


def test_unhandled_errors_and_api_documentation_headers() -> None:
    """Outer Starlette errors are safe and schema UI assets are not CSP-blocked."""

    from app.security import security_headers, unexpected_problem_handler

    app = FastAPI()
    app.add_middleware(SecurityMiddleware)
    app.add_exception_handler(Exception, unexpected_problem_handler)

    @app.get("/v1/error")
    async def fail() -> None:
        raise ValueError("private database credential")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v1/error")
        assert response.status_code == 500
        assert "private" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/problem+json"
        docs = client.get("/docs")
        assert docs.status_code == 200
        assert "content-security-policy" not in docs.headers
        assert docs.headers["x-frame-options"] == "DENY"
    assert "Content-Security-Policy" in security_headers("/v1/error")


def test_uvicorn_access_formatter_retains_structured_fields() -> None:
    """The deployed formatter must still work after credential redaction."""

    from uvicorn.logging import AccessFormatter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/v1/candidate/invites/private-token/consent", "1.1", 200),
        None,
    )
    CandidateInviteTokenFilter().filter(record)
    rendered = AccessFormatter(
        fmt='%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False
    ).format(record)
    assert "private-token" not in rendered
    assert "GET /v1/candidate/invites/[REDACTED]/consent HTTP/1.1" in rendered
    assert "200 OK" in rendered
    # Non-standard manual records still redact normally, without unpacking them.
    for args in ((), ({"value": "Bearer private-token"},)):
        manual = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, "Bearer private-token", args, None
        )
        CandidateInviteTokenFilter().filter(manual)
        assert "private-token" not in manual.getMessage()
