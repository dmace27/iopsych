"""Real PostgreSQL issuance deduplication, worker locks and populated migration upgrades."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import UUID

import pytest
from alembic import command
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.database.models import AssessmentInvite, AssessmentInviteStatus, InvitationDelivery
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_PROFILE_ID, ALPHA_ROLE_ID
from app.invitations.delivery import InvitationEmail
from app.invitations.outbox import process_delivery_batch
from app.invitations.schemas import InvitationCreateRequest
from app.invitations.service import InternalInvitationService
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET
from tests.test_database_migrations import alembic_config
from tests.test_invitation_delivery import IdempotentProvider
from tests.test_invitations import (
    RecordingDelivery,
    auth_header,
    invitation_settings,
    invite_payload,
    token_from_message,
)
from tests.test_reports_postgres import postgres_report_factory as postgres_report_factory


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio with production sync database route execution."""
    return "asyncio"


def application(factory: sessionmaker[Session]) -> FastAPI:
    """Build the same API configuration with a controlled, never-network email adapter."""
    return create_app(
        session_factory=factory,
        invitation_settings=invitation_settings(),
        invitation_delivery=RecordingDelivery(),
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET, jwt_issuer=ISSUER, jwt_audience=AUDIENCE
        ),
    )


def recruiter_headers() -> dict[str, str]:
    """Use the fixture's actual seeded subject without changing tenant data."""
    return auth_header("synthetic-alpha-recruiter", ALPHA_ORGANIZATION_ID)


@pytest.mark.anyio
async def test_concurrent_issuance_reuses_one_durable_invitation(
    postgres_report_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both requests pass auth before competing for the same organization/request key."""
    ready = Barrier(2)
    original = InternalInvitationService._issue

    def issue(
        self: InternalInvitationService,
        role_id: UUID,
        request: InvitationCreateRequest,
        *,
        replaces: UUID | None = None,
    ) -> AssessmentInvite:
        ready.wait(timeout=5)
        return original(self, role_id, request, replaces=replaces)

    monkeypatch.setattr(InternalInvitationService, "_issue", issue)
    app = application(postgres_report_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = invite_payload()

        async def create() -> dict[str, object]:
            response = await client.post(
                f"/v1/roles/{ALPHA_ROLE_ID}/invites", json=payload, headers=recruiter_headers()
            )
            assert response.status_code == 201, response.text
            result: dict[str, object] = response.json()
            return result

        first, second = await asyncio.gather(create(), create())
        assert first["id"] == second["id"]
    with postgres_report_factory() as session:
        assert session.scalar(select(func.count()).select_from(AssessmentInvite)) == 1
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 1


class BlockingProvider(IdempotentProvider):
    """Pause one external send so tests can prove another worker/revocation's behavior."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def send(self, message: InvitationEmail, *, idempotency_key: str) -> str:
        self.entered.set()
        assert self.release.wait(timeout=5), "test did not release provider"
        return super().send(message, idempotency_key=idempotency_key)


@pytest.mark.anyio
async def test_workers_skip_busy_rows_and_revocation_wins_after_inflight_send(
    postgres_report_factory: sessionmaker[Session],
) -> None:
    """A busy message is not sent by a second worker; revocation never revives its token."""
    factory = postgres_report_factory
    async with AsyncClient(
        transport=ASGITransport(app=application(factory)), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites", json=invite_payload(), headers=recruiter_headers()
        )
        assert response.status_code == 201
        invite_id = response.json()["id"]
        provider = BlockingProvider()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(process_delivery_batch, factory, invitation_settings(), provider)
            assert await asyncio.to_thread(provider.entered.wait, 5)
            try:
                assert (
                    await asyncio.to_thread(
                        process_delivery_batch, factory, invitation_settings(), IdempotentProvider()
                    )
                    == 0
                )
                revoke = asyncio.create_task(
                    client.post(
                        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{invite_id}/revoke",
                        headers=recruiter_headers(),
                    )
                )
                provider.release.set()
                assert (await revoke).status_code == 200
                assert await asyncio.to_thread(pending.result, 5) == 1
            finally:
                provider.release.set()
        assert len(provider.accepted) == 1
        token = token_from_message(provider.requests[0][1])
        assert (await client.get(f"/v1/candidate/invites/{token}")).status_code == 410
        assert process_delivery_batch(factory, invitation_settings(), provider) == 0


def test_delivery_migration_preserves_legacy_links_without_minting_jobs(
    postgres_report_factory: sessionmaker[Session],
) -> None:
    """Existing sent/active links remain unchanged when adding delivery metadata tables."""
    factory = postgres_report_factory
    with factory.begin() as session:
        invite = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="legacy@example.invalid",
            token_hash="e" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            status=AssessmentInviteStatus.ACTIVE,
        )
        session.add(invite)
        session.flush()
        invite_id = invite.id
        engine = session.get_bind()
        assert isinstance(engine, Engine)
        url = engine.url.render_as_string(hide_password=False)
    config = alembic_config(url)
    command.downgrade(config, "20261103_0008")
    command.upgrade(config, "head")
    with factory() as session:
        persisted = session.get(AssessmentInvite, invite_id)
        assert persisted is not None
        assert (
            persisted.token_hash == "e" * 64 and persisted.status == AssessmentInviteStatus.ACTIVE
        )
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 0
