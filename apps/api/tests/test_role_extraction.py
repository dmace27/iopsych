"""Structured role-extraction provider, validation, retry, and approval tests."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from email.message import Message
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.database.models import (
    AuditEvent,
    InternalUserRole,
    Role,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_USER_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.extraction.config import RoleExtractionSettings
from app.extraction.provider import (
    OpenAIStructuredRoleExtractionProvider,
    RoleExtractionInput,
    RoleExtractionProviderError,
    UnconfiguredRoleExtractionProvider,
    _extract_output_text,
    build_role_extraction_provider,
)
from app.extraction.service import StructuredRoleExtractionService
from app.main import create_app
from iopsych_contracts import CONSTRUCT_KEYS, ConstructKey
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token

ALPHA_MANAGER_ID = UUID("30000000-0000-4000-8000-000000000001")
EVIDENCE = {
    ConstructKey.AUTONOMY: "Own projects independently.",
    ConstructKey.STRUCTURE: "Follow defined goals and routines.",
    ConstructKey.AMBIGUITY: "Navigate changing requirements.",
    ConstructKey.COLLABORATION: "Partner closely with teammates.",
    ConstructKey.MASTERY: "Solve technically difficult problems.",
    ConstructKey.PACE: "Shift between urgent priorities.",
}
JOB_DESCRIPTION = " ".join(EVIDENCE.values())


class SequenceProvider:
    """Return or raise a deterministic sequence while recording bounded inputs."""

    def __init__(self, outcomes: list[object | Exception]) -> None:
        self.outcomes = outcomes
        self.inputs: list[RoleExtractionInput] = []

    def extract(self, role: RoleExtractionInput) -> object:
        """Record the safe role-only input and consume one configured outcome."""

        self.inputs.append(role)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeHttpResponse:
    """Minimal context-managed response returned by a patched ``urlopen``."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def read(self) -> bytes:
        return self.body


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for every extraction API test."""

    return "asyncio"


@pytest.fixture
def extraction_session_factory(database_engine: Engine) -> sessionmaker[Session]:
    """Seed recruiters and managers in two isolated organizations."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        recruiter = session.get(User, ALPHA_USER_ID)
        beacon = session.get(User, BEACON_USER_ID)
        assert recruiter is not None
        assert beacon is not None
        recruiter.auth_subject = "extract-alpha-recruiter"
        beacon.auth_subject = "extract-beacon-manager"
        beacon.role = InternalUserRole.RECRUITER
        session.add(
            User(
                id=ALPHA_MANAGER_ID,
                organization_id=ALPHA_ORGANIZATION_ID,
                email="extract-manager@alpha.example.invalid",
                name="Extraction Manager",
                auth_subject="extract-alpha-manager",
                role=InternalUserRole.HIRING_MANAGER,
            )
        )
        session.commit()
    return factory


def valid_extraction() -> dict[str, object]:
    """Build a complete provider response grounded in the submitted source."""

    return {
        "constructs": [
            {
                "key": key.value,
                "rating": 4 if key is ConstructKey.AUTONOMY else 3,
                "confidence": "high" if key is ConstructKey.AUTONOMY else "medium",
                "rationale": f"The description explicitly addresses {key.value}.",
                "evidence": [EVIDENCE[key]],
            }
            for key in CONSTRUCT_KEYS
        ],
        "assumptions": ["The description may not cover every working condition."],
        "needs_human_review": True,
    }


def role_payload() -> dict[str, str]:
    """Return a valid role with evidence for all six constructs."""

    return {
        "title": "Platform Engineer",
        "department": "Engineering",
        "location": "Remote",
        "job_description": JOB_DESCRIPTION,
    }


def headers(subject: str, organization_id: UUID) -> dict[str, str]:
    """Issue a tenant-bound test credential."""

    token = make_token(claims={"sub": subject, "organization_id": str(organization_id)})
    return {"Authorization": f"Bearer {token}"}


def test_settings_validate_provider_model_url_and_bounds() -> None:
    """Every environment-controlled field is validated before provider use."""

    configured = RoleExtractionSettings(
        provider=" OPENAI ",
        model=" gpt-test ",
        base_url="http://localhost:9000/v1/",
        timeout_seconds=1,
        max_attempts=1,
        retry_base_delay_seconds=0,
    )
    assert configured.provider == "openai"
    assert configured.model == "gpt-test"
    assert configured.base_url == "http://localhost:9000/v1"
    assert RoleExtractionSettings(api_key=SecretStr("   ")).api_key is None

    invalid_values = [
        {"provider": "unknown"},
        {"model": "   "},
        {"base_url": "relative"},
        {"base_url": "https://example.com/v1?debug=true"},
        {"base_url": "http://example.com/v1"},
        {"timeout_seconds": 0},
        {"max_attempts": 0},
        {"retry_base_delay_seconds": -1},
    ]
    for values in invalid_values:
        with pytest.raises(ValidationError):
            RoleExtractionSettings(**values)  # type: ignore[arg-type]


def test_provider_builder_fails_closed_without_configuration() -> None:
    """Missing credentials and explicit disablement both use the fail-closed adapter."""

    missing_key = build_role_extraction_provider(RoleExtractionSettings())
    disabled = build_role_extraction_provider(RoleExtractionSettings(provider="disabled"))
    assert isinstance(missing_key, UnconfiguredRoleExtractionProvider)
    assert isinstance(disabled, UnconfiguredRoleExtractionProvider)

    role = RoleExtractionInput("Title", "Department", "Remote", "Description")
    with pytest.raises(RoleExtractionProviderError, match="not configured") as raised:
        missing_key.extract(role)
    assert raised.value.retryable is False

    with pytest.raises(ValueError, match="API key"):
        OpenAIStructuredRoleExtractionProvider(RoleExtractionSettings())


def test_openai_adapter_sends_strict_schema_and_decodes_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTP adapter disables storage and supplies the complete strict schema."""

    captured: dict[str, Any] = {}
    output = json.dumps(valid_extraction())
    envelope = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": output}],
            }
        ]
    }

    def fake_urlopen(request: Any, *, timeout: float) -> FakeHttpResponse:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeHttpResponse(json.dumps(envelope).encode())

    monkeypatch.setattr("app.extraction.provider.urlopen", fake_urlopen)
    settings = RoleExtractionSettings(
        api_key=SecretStr("test-key"),
        model="gpt-test",
        base_url="https://provider.example/v1",
        timeout_seconds=7,
    )
    provider = build_role_extraction_provider(settings)
    role = RoleExtractionInput("Title", "Department", "Remote", JOB_DESCRIPTION)

    assert provider.extract(role) == valid_extraction()
    assert captured["url"] == "https://provider.example/v1/responses"
    assert captured["timeout"] == 7
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["store"] is False
    assert captured["body"]["text"]["format"]["strict"] is True
    assert captured["body"]["text"]["format"]["schema"]["additionalProperties"] is False
    assert json.loads(captured["body"]["input"]) == asdict(role)
    assert "candidate" not in captured["body"]["input"].lower()


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (HTTPError("https://provider.example", 429, "limited", Message(), BytesIO()), True),
        (HTTPError("https://provider.example", 408, "timeout", Message(), BytesIO()), True),
        (HTTPError("https://provider.example", 409, "conflict", Message(), BytesIO()), True),
        (HTTPError("https://provider.example", 500, "failed", Message(), BytesIO()), True),
        (HTTPError("https://provider.example", 400, "bad", Message(), BytesIO()), False),
        (URLError("offline"), True),
        (TimeoutError(), True),
    ],
)
def test_openai_adapter_classifies_transport_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, retryable: bool
) -> None:
    """Only transient HTTP and transport failures are eligible for retries."""

    def fail(*args: object, **kwargs: object) -> FakeHttpResponse:
        del args, kwargs
        raise error

    monkeypatch.setattr("app.extraction.provider.urlopen", fail)
    provider = OpenAIStructuredRoleExtractionProvider(
        RoleExtractionSettings(api_key=SecretStr("test-key"))
    )
    with pytest.raises(RoleExtractionProviderError) as raised:
        provider.extract(RoleExtractionInput("T", "D", "L", "Description"))
    assert raised.value.retryable is retryable


@pytest.mark.parametrize("body", [b"not-json", b"\xff"])
def test_openai_adapter_rejects_invalid_provider_envelopes(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    """Non-JSON and non-UTF-8 responses become retryable safe failures."""

    monkeypatch.setattr(
        "app.extraction.provider.urlopen", lambda *args, **kwargs: FakeHttpResponse(body)
    )
    provider = OpenAIStructuredRoleExtractionProvider(
        RoleExtractionSettings(api_key=SecretStr("test-key"))
    )
    with pytest.raises(RoleExtractionProviderError, match="invalid response") as raised:
        provider.extract(RoleExtractionInput("T", "D", "L", "Description"))
    assert raised.value.retryable is True


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"output": [None, {"type": "message", "content": None}]},
        {"output": [{"type": "message", "content": [{"type": "output_text", "text": ""}]}]},
    ],
)
def test_output_parser_rejects_missing_text(payload: object) -> None:
    """Malformed successful envelopes cannot be mistaken for structured output."""

    with pytest.raises(RoleExtractionProviderError) as raised:
        _extract_output_text(payload)
    assert raised.value.retryable is True


def test_output_parser_rejects_refusal_without_retry() -> None:
    """A model refusal is terminal for the request rather than retried."""

    payload = {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}]}
    with pytest.raises(RoleExtractionProviderError, match="refused") as raised:
        _extract_output_text(payload)
    assert raised.value.retryable is False


@pytest.mark.parametrize(
    "structured_text",
    ["not-json", '{"needs_human_review":true,"needs_human_review":false}'],
)
def test_openai_adapter_rejects_invalid_or_ambiguous_structured_json(
    monkeypatch: pytest.MonkeyPatch, structured_text: str
) -> None:
    """JSON syntax errors and duplicate object members both fail closed."""

    envelope = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": structured_text}],
            }
        ]
    }
    monkeypatch.setattr(
        "app.extraction.provider.urlopen",
        lambda *args, **kwargs: FakeHttpResponse(json.dumps(envelope).encode()),
    )
    provider = OpenAIStructuredRoleExtractionProvider(
        RoleExtractionSettings(api_key=SecretStr("test-key"))
    )
    with pytest.raises(RoleExtractionProviderError, match="invalid structured output"):
        provider.extract(RoleExtractionInput("T", "D", "L", "Description"))


async def make_client(
    factory: sessionmaker[Session], provider: SequenceProvider | UnconfiguredRoleExtractionProvider
) -> AsyncClient:
    """Build an authenticated app around an injected deterministic provider."""

    application = create_app(
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_leeway_seconds=0,
        ),
        session_factory=factory,
        role_extraction_settings=RoleExtractionSettings(max_attempts=3, retry_base_delay_seconds=0),
        role_extraction_provider=provider,
    )
    return AsyncClient(transport=ASGITransport(app=application), base_url="http://test")


@pytest.mark.anyio
async def test_successful_extraction_creates_only_a_manager_approvable_draft(
    extraction_session_factory: sessionmaker[Session],
) -> None:
    """Valid LLM output remains inert until the separate human approval action."""

    provider = SequenceProvider([valid_extraction()])
    client = await make_client(extraction_session_factory, provider)
    recruiter = headers("extract-alpha-recruiter", ALPHA_ORGANIZATION_ID)
    manager = headers("extract-alpha-manager", ALPHA_ORGANIZATION_ID)
    async with client:
        created = await client.post("/v1/roles", headers=recruiter, json=role_payload())
        role_id = created.json()["id"]
        manager_extract = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=manager)
        assert manager_extract.status_code == 403

        extracted = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=recruiter)
        assert extracted.status_code == 201
        profile = extracted.json()
        assert profile["status"] == "draft"
        assert profile["approved_by"] is None
        assert profile["approved_at"] is None
        assert profile["assumptions"] == ["The description may not cover every working condition."]
        assert len(profile["constructs"]) == 6

        recruiter_approval = await client.post(
            f"/v1/roles/{role_id}/profiles/{profile['id']}/approve", headers=recruiter
        )
        assert recruiter_approval.status_code == 403
        before_approval = await client.get(f"/v1/roles/{role_id}", headers=recruiter)
        assert before_approval.json()["status"] == "draft"

        approved = await client.post(
            f"/v1/roles/{role_id}/profiles/{profile['id']}/approve", headers=manager
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["assumptions"] == profile["assumptions"]

    assert len(provider.inputs) == 1
    assert asdict(provider.inputs[0]) == role_payload()
    with extraction_session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "role_profile.extraction_requested",
                AuditEvent.entity_id == UUID(profile["id"]),
            )
        )
        assert event is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload["constructs"][0].update({"rating": 6}),
        lambda payload: payload["constructs"][0].update({"rating": "3"}),
        lambda payload: payload["constructs"][0].update({"confidence": "certain"}),
        lambda payload: payload["constructs"][0].update({"evidence": ["Unsupported"]}),
        lambda payload: payload.update({"needs_human_review": False}),
        lambda payload: payload.update({"needs_human_review": 1}),
        lambda payload: payload["constructs"].pop(),
    ],
)
async def test_invalid_provider_fields_are_retried_then_rejected_without_a_draft(
    extraction_session_factory: sessionmaker[Session], mutate: Any
) -> None:
    """All structural and source-grounding failures exhaust safely and persist nothing."""

    invalid = deepcopy(valid_extraction())
    mutate(invalid)
    provider = SequenceProvider([deepcopy(invalid), deepcopy(invalid), deepcopy(invalid)])
    client = await make_client(extraction_session_factory, provider)
    recruiter = headers("extract-alpha-recruiter", ALPHA_ORGANIZATION_ID)
    async with client:
        created = await client.post("/v1/roles", headers=recruiter, json=role_payload())
        role_id = created.json()["id"]
        response = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=recruiter)
        history = await client.get(f"/v1/roles/{role_id}/profiles", headers=recruiter)

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "role_extraction_failed"
    assert "provider" not in response.json()["detail"].lower()
    assert history.json() == []
    assert len(provider.inputs) == 3


@pytest.mark.anyio
async def test_transient_and_invalid_outputs_retry_until_success(
    extraction_session_factory: sessionmaker[Session],
) -> None:
    """Transient transport and schema failures can recover within the configured bound."""

    provider = SequenceProvider(
        [
            RoleExtractionProviderError("temporary secret detail", retryable=True),
            {"invalid": "shape"},
            valid_extraction(),
        ]
    )
    client = await make_client(extraction_session_factory, provider)
    recruiter = headers("extract-alpha-recruiter", ALPHA_ORGANIZATION_ID)
    async with client:
        role = await client.post("/v1/roles", headers=recruiter, json=role_payload())
        response = await client.post(
            f"/v1/roles/{role.json()['id']}/extract-profile", headers=recruiter
        )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert len(provider.inputs) == 3


@pytest.mark.anyio
async def test_nonretryable_unconfigured_foreign_and_archived_requests_fail_safely(
    extraction_session_factory: sessionmaker[Session],
) -> None:
    """Configuration, tenant, and lifecycle gates run before unsafe provider use."""

    recruiter = headers("extract-alpha-recruiter", ALPHA_ORGANIZATION_ID)
    beacon = headers("extract-beacon-manager", BEACON_ORGANIZATION_ID)

    unconfigured = UnconfiguredRoleExtractionProvider()
    client = await make_client(extraction_session_factory, unconfigured)
    async with client:
        role = await client.post("/v1/roles", headers=recruiter, json=role_payload())
        role_id = role.json()["id"]
        unavailable = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=recruiter)
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "role_extraction_unavailable"

    provider = SequenceProvider([RoleExtractionProviderError("do not expose", retryable=False)])
    client = await make_client(extraction_session_factory, provider)
    async with client:
        foreign = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=beacon)
        failed = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=recruiter)
        archived_response = await client.delete(f"/v1/roles/{role_id}", headers=recruiter)
        archived = await client.post(f"/v1/roles/{role_id}/extract-profile", headers=recruiter)
    assert foreign.status_code == 404
    assert failed.status_code == 502
    assert archived_response.status_code == 204
    assert archived.status_code == 409
    assert archived.json()["code"] == "role_archived"
    assert len(provider.inputs) == 1


def test_retry_backoff_is_bounded_and_exponential(
    extraction_session_factory: sessionmaker[Session],
) -> None:
    """Configured retries use bounded exponential delays before successful persistence."""

    provider = SequenceProvider(
        [RoleExtractionProviderError("temporary", retryable=True), valid_extraction()]
    )
    delays: list[float] = []
    settings = RoleExtractionSettings(
        max_attempts=2,
        retry_base_delay_seconds=0.25,
    )
    context = AuthorizationContext(
        user_id=ALPHA_USER_ID,
        email="recruiter@alpha.example.invalid",
        name="Alpha Recruiter",
        role=InternalUserRole.RECRUITER,
        organization=OrganizationScope(organization_id=ALPHA_ORGANIZATION_ID),
    )
    with extraction_session_factory() as session:
        role = Role(
            organization_id=ALPHA_ORGANIZATION_ID,
            title="Platform Engineer",
            department="Engineering",
            location="Remote",
            job_description=JOB_DESCRIPTION,
            status=RoleStatus.DRAFT,
        )
        session.add(role)
        session.commit()
        profile = StructuredRoleExtractionService(
            session,
            context,
            provider,
            settings,
            sleeper=delays.append,
        ).extract(role.id)
        profile_count = session.scalar(
            select(func.count()).select_from(RoleProfile).where(RoleProfile.role_id == role.id)
        )

    assert delays == [0.25]
    assert profile.status is RoleProfileStatus.DRAFT
    assert profile_count == 1


@pytest.mark.anyio
async def test_audit_commit_failure_rolls_back_extracted_profile(
    extraction_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A required audit failure must not leave an unreported draft behind."""

    with extraction_session_factory() as session:
        role = Role(
            organization_id=ALPHA_ORGANIZATION_ID,
            title="Platform Engineer",
            department="Engineering",
            location="Remote",
            job_description=JOB_DESCRIPTION,
            status=RoleStatus.DRAFT,
        )
        session.add(role)
        session.commit()
        role_id = role.id

    original_commit = Session.commit

    def fail_extraction_audit_commit(session: Session) -> None:
        if any(
            isinstance(item, AuditEvent) and item.event_type == "role_profile.extraction_requested"
            for item in session.new
        ):
            raise OperationalError("audit insert", {}, Exception("offline"))
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_extraction_audit_commit)
    client = await make_client(extraction_session_factory, SequenceProvider([valid_extraction()]))
    recruiter = headers("extract-alpha-recruiter", ALPHA_ORGANIZATION_ID)
    async with client:
        response = await client.post(
            f"/v1/roles/{role_id}/extract-profile",
            headers=recruiter,
        )

    assert response.status_code == 500
    assert response.json()["code"] == "audit_persistence_failed"
    with extraction_session_factory() as session:
        profile_count = session.scalar(
            select(func.count()).select_from(RoleProfile).where(RoleProfile.role_id == role_id)
        )
        audit_count = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_type == "role_profile.extraction_requested")
        )
    assert profile_count == 0
    assert audit_count == 0
