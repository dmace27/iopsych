"""Synthetic resource-boundary tests; never contact a provider or external database."""

from __future__ import annotations

import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from io import BytesIO
from threading import Event
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from app.auth.errors import AccessProblemError
from app.database.models import RoleStatus
from app.extraction.config import RoleExtractionSettings
from app.extraction.provider import (
    OpenAIStructuredRoleExtractionProvider,
    RoleExtractionInput,
    RoleExtractionProviderError,
    _extraction_deadline,
)
from app.extraction.service import StructuredRoleExtractionService
from tests.test_role_extraction import JOB_DESCRIPTION, SequenceProvider, valid_extraction

ROLE = RoleExtractionInput("Title", "Department", "Remote", JOB_DESCRIPTION)


def settings(**kwargs: Any) -> RoleExtractionSettings:
    return RoleExtractionSettings(_env_file=None, api_key=SecretStr("synthetic-secret"), **kwargs)


def envelope(text: str) -> bytes:
    return json.dumps(
        {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
    ).encode()


@pytest.mark.parametrize(
    "field,invalid",
    [
        ("total_budget_seconds", 0),
        ("total_budget_seconds", 121),
        ("total_budget_seconds", float("nan")),
        ("total_budget_seconds", float("inf")),
        ("max_response_bytes", 0),
        ("max_response_bytes", 8_388_609),
        ("max_output_bytes", 0),
        ("max_output_bytes", 1_048_577),
        ("max_output_tokens", 15),
        ("max_output_tokens", 32769),
        ("max_concurrent_requests", 0),
        ("max_concurrent_requests", 33),
    ],
)
def test_settings_reject_unbounded_values(field: str, invalid: object) -> None:
    with pytest.raises(ValidationError):
        settings(**{field: invalid})


def test_response_read_is_bounded_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    response = BytesIO(b"x" * 1000)
    sizes: list[int] = []
    original = response.read

    def read(size: int = -1) -> bytes:
        sizes.append(size)
        return original(size)

    response.read = read  # type: ignore[method-assign]
    monkeypatch.setattr("app.extraction.provider.urlopen", lambda *a, **kw: response)
    with pytest.raises(RoleExtractionProviderError, match="too large") as caught:
        OpenAIStructuredRoleExtractionProvider(settings(max_response_bytes=32)).extract(ROLE)
    assert caught.value.retryable is False
    assert sizes == [33]
    assert response.closed


@pytest.mark.parametrize("extra", [0, 1])
def test_exact_envelope_boundary(monkeypatch: pytest.MonkeyPatch, extra: int) -> None:
    body = envelope("{}")
    monkeypatch.setattr("app.extraction.provider.urlopen", lambda *a, **kw: BytesIO(body))
    provider = OpenAIStructuredRoleExtractionProvider(
        settings(max_response_bytes=len(body) - extra)
    )
    if extra:
        with pytest.raises(RoleExtractionProviderError, match="too large"):
            provider.extract(ROLE)
    else:
        assert provider.extract(ROLE) == {}


@pytest.mark.parametrize("text,limit,success", [('"é"', 4, True), ('"é"', 3, False)])
def test_output_limit_counts_utf8_bytes(
    monkeypatch: pytest.MonkeyPatch, text: str, limit: int, success: bool
) -> None:
    monkeypatch.setattr("app.extraction.provider.urlopen", lambda *a, **kw: BytesIO(envelope(text)))
    provider = OpenAIStructuredRoleExtractionProvider(settings(max_output_bytes=limit))
    if success:
        assert provider.extract(ROLE) == "é"
    else:
        with pytest.raises(RoleExtractionProviderError, match="output too large") as caught:
            provider.extract(ROLE)
        assert not caught.value.retryable


@pytest.mark.parametrize("text", ['"\ud800"', "[" * 2000])
def test_malformed_output_is_safe(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr("app.extraction.provider.urlopen", lambda *a, **kw: BytesIO(envelope(text)))
    with pytest.raises(RoleExtractionProviderError, match="invalid structured output"):
        OpenAIStructuredRoleExtractionProvider(settings()).extract(ROLE)


def test_socket_timeout_and_late_response(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.extraction.provider.time.monotonic", lambda: clock[0])
    captured: dict[str, Any] = {}
    response = BytesIO(envelope("{}"))

    def transport(request: Any, *, timeout: float) -> BytesIO:
        captured.update(timeout=timeout, body=json.loads(request.data))
        clock[0] += 6
        return response

    monkeypatch.setattr("app.extraction.provider.urlopen", transport)
    token = _extraction_deadline.set(105)
    try:
        with pytest.raises(RoleExtractionProviderError, match="budget exhausted"):
            OpenAIStructuredRoleExtractionProvider(settings(max_output_tokens=128)).extract(ROLE)
    finally:
        _extraction_deadline.reset(token)
    assert captured["timeout"] == 5
    assert captured["body"]["max_output_tokens"] == 128
    assert response.closed


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("synthetic-secret"),
        OSError("synthetic-secret"),
        HTTPError(
            "https://synthetic-secret", 429, "synthetic-secret", Message(), BytesIO(b"secret")
        ),
    ],
)
def test_transport_errors_do_not_expose_details(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def transport(*args: Any, **kwargs: Any) -> BytesIO:
        raise error

    monkeypatch.setattr("app.extraction.provider.urlopen", transport)
    with pytest.raises(RoleExtractionProviderError) as caught:
        OpenAIStructuredRoleExtractionProvider(settings()).extract(ROLE)
    assert caught.value.retryable
    assert "synthetic-secret" not in "".join(traceback.format_exception(caught.value))
    if isinstance(error, HTTPError):
        assert error.closed


class Profiles:
    def __init__(self) -> None:
        self.created = 0

    def get_role(self, role_id: object) -> SimpleNamespace:
        return SimpleNamespace(status=RoleStatus.DRAFT, **ROLE.__dict__)

    def create_profile(self, *args: Any, **kwargs: Any) -> str:
        self.created += 1
        return "draft"


def service(provider: Any, **kwargs: Any) -> StructuredRoleExtractionService:
    # Replace only persistence; exercise the real service admission/retry/semantic path.
    result = object.__new__(StructuredRoleExtractionService)
    result._profiles = Profiles()  # type: ignore[assignment]
    result._provider = provider
    result._settings = settings(**kwargs)
    result._sleeper = lambda delay: None
    return result


def test_retry_budget_includes_backoff_and_releases_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.extraction.service.time.monotonic", lambda: clock[0])
    provider = SequenceProvider([RoleExtractionProviderError("secret", retryable=True)] * 3)
    runner = service(provider, total_budget_seconds=1, retry_base_delay_seconds=1)
    sleeps: list[float] = []
    runner._sleeper = sleeps.append
    with pytest.raises(AccessProblemError):
        runner.extract(uuid4())
    assert len(provider.inputs) == 1
    assert not sleeps
    assert _extraction_deadline.get() is None
    assert runner._profiles.created == 0  # type: ignore[attr-defined]


def test_retry_timeout_shrinks_with_remaining_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    timeouts: list[float] = []
    monkeypatch.setattr("app.extraction.service.time.monotonic", lambda: clock[0])

    def transport(*args: Any, timeout: float) -> BytesIO:
        timeouts.append(timeout)
        clock[0] += 3
        raise TimeoutError("secret")

    monkeypatch.setattr("app.extraction.provider.urlopen", transport)
    runner = service(
        OpenAIStructuredRoleExtractionProvider(settings()),
        total_budget_seconds=5,
        retry_base_delay_seconds=0,
    )
    with pytest.raises(AccessProblemError):
        runner.extract(uuid4())
    assert timeouts == [5, 2]


def test_late_valid_candidate_is_not_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.extraction.service.time.monotonic", lambda: clock[0])

    class SlowProvider:
        def extract(self, role: RoleExtractionInput) -> object:
            clock[0] += 10
            return valid_extraction()

    runner = service(SlowProvider(), total_budget_seconds=1)
    with pytest.raises(AccessProblemError):
        runner.extract(uuid4())
    assert runner._profiles.created == 0  # type: ignore[attr-defined]


@pytest.mark.parametrize("same_role,limit", [(True, 4), (False, 1)])
def test_concurrent_and_duplicate_calls_fail_fast_and_release(same_role: bool, limit: int) -> None:
    entered, release = Event(), Event()

    class BlockingProvider:
        def extract(self, role: RoleExtractionInput) -> object:
            entered.set()
            assert release.wait(3)
            return valid_extraction()

    first_id = uuid4()
    first = service(BlockingProvider(), max_concurrent_requests=limit)
    second_provider = SequenceProvider([valid_extraction()])
    second = service(second_provider, max_concurrent_requests=limit)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(first.extract, first_id)
        try:
            assert entered.wait(3)
            with pytest.raises(AccessProblemError) as caught:
                second.extract(first_id if same_role else uuid4())
            assert caught.value.code == "role_extraction_failed"
            assert not second_provider.inputs
        finally:
            release.set()
        assert pending.result(timeout=3) == "draft"
    assert second.extract(first_id) == "draft"


def test_failure_frees_admission_and_redacts_traceback() -> None:
    runner = service(
        SequenceProvider(
            [RoleExtractionProviderError("synthetic-secret", retryable=False), valid_extraction()]
        ),
        max_concurrent_requests=1,
    )
    role_id = uuid4()
    with pytest.raises(AccessProblemError) as caught:
        runner.extract(role_id)
    assert "synthetic-secret" not in "".join(traceback.format_exception(caught.value))
    assert runner.extract(role_id) == "draft"


def test_stalled_read_is_closed_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    class StalledResponse(BytesIO):
        def read(self, size: int = -1) -> bytes:
            assert size > 0
            raise TimeoutError("synthetic-secret")

    response = StalledResponse()
    monkeypatch.setattr("app.extraction.provider.urlopen", lambda *a, **kw: response)
    with pytest.raises(RoleExtractionProviderError) as caught:
        OpenAIStructuredRoleExtractionProvider(settings()).extract(ROLE)
    assert caught.value.retryable
    assert response.closed
    assert "synthetic-secret" not in "".join(traceback.format_exception(caught.value))


def test_expired_deadline_never_opens_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("expired work must not call transport")

    monkeypatch.setattr("app.extraction.provider.urlopen", forbidden)
    token = _extraction_deadline.set(0)
    try:
        with pytest.raises(RoleExtractionProviderError, match="budget exhausted"):
            OpenAIStructuredRoleExtractionProvider(settings()).extract(ROLE)
    finally:
        _extraction_deadline.reset(token)


def test_oversized_output_is_not_retried_or_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def transport(*args: Any, **kwargs: Any) -> BytesIO:
        calls.append(1)
        return BytesIO(envelope('"12345"'))

    monkeypatch.setattr("app.extraction.provider.urlopen", transport)
    runner = service(OpenAIStructuredRoleExtractionProvider(settings(max_output_bytes=3)))
    with pytest.raises(AccessProblemError):
        runner.extract(uuid4())
    assert calls == [1]
    assert runner._profiles.created == 0  # type: ignore[attr-defined]


def test_overslept_backoff_does_not_start_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.extraction.service.time.monotonic", lambda: clock[0])
    provider = SequenceProvider([RoleExtractionProviderError("secret", retryable=True)])
    runner = service(provider, total_budget_seconds=2, retry_base_delay_seconds=1)

    def oversleep(delay: float) -> None:
        clock[0] += delay + 2

    runner._sleeper = oversleep
    with pytest.raises(AccessProblemError):
        runner.extract(uuid4())
    assert len(provider.inputs) == 1
