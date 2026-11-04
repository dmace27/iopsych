"""Synthetic privacy and correlation checks for bounded completion telemetry."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.routing import Route
from starlette.types import Message, Receive, Scope, Send

from app.main import create_app
from app.runtime.config import RuntimeSettings
from app.runtime.telemetry import CompletionTelemetryMiddleware, correlation_headers

LOGGER = "app.runtime.telemetry"
SENSITIVE = "synthetic-private-value"
FIELDS = {"event", "request_id", "method", "route", "status_class", "duration_ms", "release_id"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    result = []
    for record in caplog.records:
        if record.name != LOGGER:
            continue
        assert record.exc_info is None
        assert record.stack_info is None
        payload = json.loads(record.getMessage())
        assert set(payload) == FIELDS
        assert payload["event"] == "request_completed"
        assert UUID(payload["request_id"]).version == 4
        assert 0 <= payload["duration_ms"] <= 86_400_000
        assert SENSITIVE not in record.getMessage()
        result.append(payload)
    return result


@pytest.mark.parametrize("incoming", [SENSITIVE, "not-a-uuid\tvalue", str(uuid4()), ""])
def test_server_owned_id_and_sensitive_inputs(
    incoming: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IOPSYCH_RELEASE_ID", "build-123.abc_4")
    caplog.set_level(logging.INFO, logger=LOGGER)
    factory = MagicMock(spec=sessionmaker)
    application = create_app(session_factory=factory)

    @application.post("/test-candidate/{token}")
    async def candidate(token: str, request: Request) -> dict[str, bool]:
        await request.body()
        return {"ok": True}

    with TestClient(application) as client:
        responses = [
            client.post(
                f"/test-candidate/{SENSITIVE}?email={SENSITIVE}@example.test",
                content=f"user={SENSITIVE};org={SENSITIVE}",
                headers={
                    "X-Request-ID": incoming,
                    "Authorization": f"Bearer {SENSITIVE}",
                    "Cookie": f"session={SENSITIVE}",
                    "X-Forwarded-For": "192.0.2.13",
                    "User-Agent": SENSITIVE,
                },
            )
            for _ in range(2)
        ]
    entries = records(caplog)
    assert len(entries) == 2
    assert entries[0]["request_id"] != entries[1]["request_id"]
    for response, entry in zip(responses, entries, strict=True):
        assert response.status_code == 200
        assert response.headers["x-request-id"] == entry["request_id"] != incoming
        assert entry["route"] == "/test-candidate/{token}"
        assert entry["method"] == "POST"
        assert entry["status_class"] == "2xx"
        assert entry["release_id"] == "build-123.abc_4"
    assert "192.0.2.13" not in str(entries)
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("path", "template", "status"),
    [
        (f"/v1/candidate/invites/{SENSITIVE}", "/v1/candidate/invites/{token}", 503),
        (f"/missing/{SENSITIVE}", "unmatched", 404),
        (f"/v1/candidate/invites/{SENSITIVE}/missing", "unmatched", 404),
    ],
)
def test_actual_candidate_and_unknown_routes(
    path: str, template: str, status: int, caplog: pytest.LogCaptureFixture
) -> None:
    application = create_app(session_factory=MagicMock(spec=sessionmaker))
    with TestClient(application) as client:
        response = client.get(path, params={"private": SENSITIVE})
    assert response.status_code == status
    (entry,) = records(caplog)
    assert entry["route"] == template
    assert entry["request_id"] == response.headers["x-request-id"]


def test_500_is_correlated_once_without_exception_text(caplog: pytest.LogCaptureFixture) -> None:
    application = create_app(session_factory=MagicMock(spec=sessionmaker))

    @application.get("/test-failure/{token}")
    async def fail(token: str) -> None:
        raise RuntimeError(f"{SENSITIVE} email@example.test 192.0.2.10")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(f"/test-failure/{SENSITIVE}")
    assert response.status_code == 500
    assert SENSITIVE not in response.text
    (entry,) = records(caplog)
    assert entry["route"] == "/test-failure/{token}"
    assert entry["status_class"] == "5xx"
    assert entry["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("status", [408, 413])
@pytest.mark.anyio
async def test_early_limits_correlated_before_routing(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    factory = MagicMock(spec=sessionmaker)
    application = create_app(
        session_factory=factory,
        runtime_settings=RuntimeSettings(max_request_body_bytes=4, request_body_timeout_seconds=1),
    )
    sent: list[Message] = []

    async def receive() -> Message:
        if status == 408:
            await asyncio.sleep(2)
        return {"type": "http.request", "body": b"12345", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    await application(
        {
            "type": "http",
            "method": "POST",
            "path": f"/v1/candidate/invites/{SENSITIVE}",
            "query_string": SENSITIVE.encode(),
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("192.0.2.1", 42),
            "http_version": "1.1",
        },
        receive,
        send,
    )
    assert sent[0]["status"] == status
    (entry,) = records(caplog)
    assert entry["route"] == "unmatched"
    assert entry["status_class"] == "4xx"
    assert dict(sent[0]["headers"])[b"x-request-id"].decode() == entry["request_id"]
    factory.assert_not_called()


@pytest.mark.parametrize(
    "release", ["", "a" * 65, "bad\nrelease", "mail@example.test", "../bad", "é"]
)
def test_release_allowlist(release: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOPSYCH_RELEASE_ID", release)
    assert CompletionTelemetryMiddleware(AsyncMock(), routes=[]).release_id == "unknown"


@pytest.mark.parametrize("release", ["a", "a" * 64, "2026-11-04.abc_12"])
def test_valid_release(release: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOPSYCH_RELEASE_ID", release)
    assert CompletionTelemetryMiddleware(AsyncMock(), routes=[]).release_id == release


@pytest.mark.parametrize("mode", ["disconnect", "cancel", "cancel_after_start", "incomplete"])
@pytest.mark.anyio
async def test_incomplete_requests_never_claim_success(
    mode: str, caplog: pytest.LogCaptureFixture
) -> None:
    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        if mode in {"cancel_after_start", "incomplete"}:
            await send({"type": "http.response.start", "status": 200, "headers": []})
        if mode.startswith("cancel"):
            raise asyncio.CancelledError

    middleware = CompletionTelemetryMiddleware(application, routes=[])
    scope: Scope = {"type": "http", "method": SENSITIVE}
    if mode.startswith("cancel"):
        with pytest.raises(asyncio.CancelledError):
            await middleware(scope, AsyncMock(), AsyncMock())
    else:
        await middleware(scope, AsyncMock(), AsyncMock())
    (entry,) = records(caplog)
    assert entry["status_class"] == "unknown"
    assert entry["method"] == "OTHER"


@pytest.mark.anyio
async def test_non_http_passthrough() -> None:
    downstream = AsyncMock()
    middleware = CompletionTelemetryMiddleware(downstream, routes=[])
    scope: Scope = {"type": "lifespan"}
    receive, send = AsyncMock(), AsyncMock()
    await middleware(scope, receive, send)
    downstream.assert_awaited_once_with(scope, receive, send)
    assert correlation_headers(scope) == {}
    assert correlation_headers({"telemetry_request_id": SENSITIVE}) == {}


@pytest.mark.anyio
async def test_route_snapshot_and_header_overwrite(caplog: pytest.LogCaptureFixture) -> None:
    route = Route("/safe/{token}", endpoint=AsyncMock())

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        scope["route"] = route
        route.path = SENSITIVE
        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [(b"X-Request-ID", SENSITIVE.encode())],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    middleware = CompletionTelemetryMiddleware(application, routes=[route])
    send = AsyncMock()
    await middleware({"type": "http", "method": "GET"}, AsyncMock(), send)
    (entry,) = records(caplog)
    assert entry["route"] == "/safe/{token}"
    assert send.call_args_list[0].args[0]["headers"] == [
        (b"x-request-id", str(entry["request_id"]).encode())
    ]


@pytest.mark.parametrize(("elapsed", "expected"), [(-1.0, 0), (0.125, 125), (1e9, 86_400_000)])
@pytest.mark.anyio
async def test_duration_is_bounded(
    elapsed: float,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    ticks = iter([10.0, 10.0 + elapsed])
    monkeypatch.setattr("app.runtime.telemetry.monotonic", lambda: next(ticks))
    middleware = CompletionTelemetryMiddleware(AsyncMock(), routes=[])
    await middleware({"type": "http", "method": "GET"}, AsyncMock(), AsyncMock())
    (entry,) = records(caplog)
    assert entry["duration_ms"] == expected


def test_included_prefix_template(caplog: pytest.LogCaptureFixture) -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/item/{token}")
    async def item(token: str) -> dict[str, bool]:
        return {"ok": True}

    application = create_app(session_factory=MagicMock(spec=sessionmaker))
    application.include_router(router, prefix="/test-prefix")
    with TestClient(application) as client:
        assert client.get(f"/test-prefix/item/{SENSITIVE}").status_code == 200
    (entry,) = records(caplog)
    assert entry["route"] == "/test-prefix/item/{token}"
