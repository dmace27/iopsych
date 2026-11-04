"""Actual-byte upload boundaries and safe database-only operational probes."""

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import Message, Receive, Scope, Send

from app.database.session import create_session_factory
from app.main import create_app
from app.runtime.config import RuntimeSettings
from app.runtime.middleware import RequestBodyLimitMiddleware
from iopsych_contracts import ApiProblem


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize(
    ("chunks", "headers", "expected"),
    [
        ([b"ab", b"cd"], [], 204),
        ([b"ab", b"cde"], [], 413),
        ([b"ab", b"cde"], [(b"content-length", b"1")], 413),
        ([b"ab", b"cd"], [(b"content-length", b"999999999")], 204),
        ([b"ab", b"cde"], [(b"transfer-encoding", b"chunked")], 413),
        ([b"", b"", b"abcd"], [], 204),
        ([b"abcde"], [], 413),
        (["éé".encode()], [], 204),
        (["ééa".encode()], [], 413),
    ],
)
@pytest.mark.anyio
async def test_actual_byte_limit(
    chunks: list[bytes], headers: list[tuple[bytes, bytes]], expected: int
) -> None:
    """Headers cannot bypass the bound and permitted chunks replay intact once."""
    messages: list[Message] = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]
    sent: list[Message] = []
    invoked = False

    async def receive() -> Message:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal invoked
        invoked = True
        assert await receive() == {
            "type": "http.request",
            "body": b"".join(chunks),
            "more_body": False,
        }
        assert await receive() == {"type": "http.disconnect"}
        await send({"type": "http.response.start", "status": 204, "headers": []})

    middleware = RequestBodyLimitMiddleware(
        application, settings=RuntimeSettings(max_request_body_bytes=4)
    )
    await middleware({"type": "http", "path": "/private-token", "headers": headers}, receive, send)
    assert sent[0]["status"] == expected
    assert invoked is (expected == 204)
    if expected == 413:
        problem = ApiProblem.model_validate_json(sent[1]["body"])
        assert problem.code == "request_body_too_large"
        assert b"private-token" not in sent[1]["body"]
        assert (b"cache-control", b"no-store") in sent[0]["headers"]


@pytest.mark.anyio
async def test_disconnect_cancellation_and_non_http() -> None:
    """Never run application work after a partial disconnect or swallow cancellation."""
    downstream = AsyncMock()
    send = AsyncMock()
    middleware = RequestBodyLimitMiddleware(downstream, settings=RuntimeSettings())
    receive = AsyncMock(
        side_effect=[
            {"type": "http.request", "body": b"partial", "more_body": True},
            {"type": "http.disconnect"},
        ]
    )
    await middleware({"type": "http", "path": "/"}, receive, send)
    downstream.assert_not_called()
    send.assert_not_called()
    with pytest.raises(asyncio.CancelledError):
        await middleware(
            {"type": "http", "path": "/"},
            AsyncMock(side_effect=asyncio.CancelledError),
            send,
        )
    scope = {"type": "lifespan"}
    await middleware(scope, receive, send)
    downstream.assert_awaited_once_with(scope, receive, send)


@pytest.mark.parametrize("chunk_delay", [0.4, 5])
@pytest.mark.anyio
async def test_total_body_deadline(chunk_delay: float) -> None:
    """A trickling stream cannot reset the total upload deadline."""
    downstream = AsyncMock()
    sent: list[Message] = []
    calls = 0

    async def receive() -> Message:
        nonlocal calls
        calls += 1
        await asyncio.sleep(chunk_delay)
        return {"type": "http.request", "body": b"x", "more_body": True}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(
        downstream, settings=RuntimeSettings(request_body_timeout_seconds=1)
    )
    await asyncio.wait_for(middleware({"type": "http", "path": "/"}, receive, send), 3)
    assert calls == (3 if chunk_delay == 0.4 else 1)
    assert sent[0]["status"] == 408
    assert json.loads(sent[1]["body"])["code"] == "request_body_timeout"
    downstream.assert_not_called()


def test_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_MAX_REQUEST_BODY_BYTES", "2048")
    monkeypatch.setenv("RUNTIME_REQUEST_BODY_TIMEOUT_SECONDS", "10")
    settings = RuntimeSettings()
    assert settings.max_request_body_bytes == 2048
    assert settings.request_body_timeout_seconds == 10
    for value in (0, 16_777_217):
        with pytest.raises(ValidationError):
            RuntimeSettings(max_request_body_bytes=value)
    for duration in (0, 121, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            RuntimeSettings(request_body_timeout_seconds=duration)


def test_readiness_success_and_ordinary_body(database_engine: Engine) -> None:
    application = create_app(session_factory=create_session_factory(database_engine))

    @application.post("/body-echo")
    async def echo(request: Request) -> dict[str, object]:
        return {"payload": await request.json()}

    with TestClient(application) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready", "service": "api"}
        assert ready.headers["cache-control"] == "no-store"
        assert client.post("/body-echo", json={"synthetic": "é"}).json() == {
            "payload": {"synthetic": "é"}
        }


def test_readiness_failure_is_safe_and_liveness_independent() -> None:
    session = MagicMock(spec=Session)
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("secret-db-url"))
    factory = MagicMock(spec=sessionmaker)
    factory.return_value.__enter__.return_value = session
    application = create_app(session_factory=factory)
    with TestClient(application) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "api",
            "version": "0.1.0",
        }
        factory.assert_not_called()
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "service": "api"}
        assert "secret" not in response.text
        assert response.headers["cache-control"] == "no-store"
        factory.return_value.__exit__.assert_called_once()


@pytest.mark.anyio
async def test_slow_probe_leaves_event_loop_available() -> None:
    """Offload is tested independently from driver deadlines, which remain open."""
    started = threading.Event()
    release = threading.Event()
    session = MagicMock(spec=Session)

    def execute(statement: object) -> None:
        started.set()
        assert release.wait(5)

    session.execute.side_effect = execute
    factory = MagicMock(spec=sessionmaker)
    factory.return_value.__enter__.return_value = session
    application = create_app(session_factory=factory)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        probe = asyncio.create_task(client.get("/ready"))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            health = await asyncio.wait_for(client.get("/health"), 1)
            assert health.status_code == 200
        finally:
            release.set()
            assert (await probe).status_code == 200


def test_oversized_body_rejected_before_route_or_database() -> None:
    factory = MagicMock(spec=sessionmaker)
    application = create_app(
        session_factory=factory, runtime_settings=RuntimeSettings(max_request_body_bytes=4)
    )
    with TestClient(application) as client:
        response = client.post("/v1/roles", content=b"12345")
        assert response.status_code == 413
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-type"] == "application/problem+json"
        factory.assert_not_called()
