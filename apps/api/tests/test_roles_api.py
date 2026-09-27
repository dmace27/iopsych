"""End-to-end API tests for role CRUD and immutable profile approval."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.database.models import (
    AuditEvent,
    InternalUserRole,
    RoleConstructRating,
    RoleProfile,
    RoleProfileStatus,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_USER_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.main import create_app
from iopsych_contracts import CONSTRUCT_KEYS, ConstructKey
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token

ALPHA_MANAGER_ID = UUID("20000000-0000-4000-8000-000000000001")
ALPHA_ADMIN_ID = UUID("20000000-0000-4000-8000-000000000002")
UNKNOWN_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")

EVIDENCE = {
    ConstructKey.AUTONOMY: "Own projects independently.",
    ConstructKey.STRUCTURE: "Follow defined goals and routines.",
    ConstructKey.AMBIGUITY: "Navigate changing requirements.",
    ConstructKey.COLLABORATION: "Partner closely with teammates.",
    ConstructKey.MASTERY: "Solve technically difficult problems.",
    ConstructKey.PACE: "Shift between urgent priorities.",
}
JOB_DESCRIPTION = " ".join(EVIDENCE.values())


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for every role API test."""

    return "asyncio"


@pytest.fixture
def role_session_factory(database_engine: Engine) -> sessionmaker[Session]:
    """Seed two tenants and all three Alpha authorization roles."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        session.commit()
        alpha_recruiter = session.get(User, ALPHA_USER_ID)
        beacon_manager = session.get(User, BEACON_USER_ID)
        assert alpha_recruiter is not None
        assert beacon_manager is not None
        alpha_recruiter.auth_subject = "provider-alpha-recruiter"
        beacon_manager.auth_subject = "provider-beacon-manager"
        session.add_all(
            [
                User(
                    id=ALPHA_MANAGER_ID,
                    organization_id=ALPHA_ORGANIZATION_ID,
                    email="manager@alpha.example.invalid",
                    name="Alpha Manager",
                    auth_subject="provider-alpha-manager",
                    role=InternalUserRole.HIRING_MANAGER,
                ),
                User(
                    id=ALPHA_ADMIN_ID,
                    organization_id=ALPHA_ORGANIZATION_ID,
                    email="admin@alpha.example.invalid",
                    name="Alpha Admin",
                    auth_subject="provider-alpha-admin",
                    role=InternalUserRole.ADMIN,
                ),
            ]
        )
        session.commit()
    return factory


@pytest.fixture
def role_app(role_session_factory: sessionmaker[Session]) -> FastAPI:
    """Build an authenticated application over the isolated role database."""

    return create_app(
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_leeway_seconds=0,
        ),
        session_factory=role_session_factory,
    )


@pytest.fixture
async def role_client(role_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Provide an in-process HTTP client for role workflow tests."""

    async with AsyncClient(transport=ASGITransport(app=role_app), base_url="http://test") as client:
        yield client


def auth_header(subject: str, organization_id: UUID) -> dict[str, str]:
    """Issue a signed test credential for one provisioned tenant identity."""

    token = make_token(
        claims={"sub": subject, "organization_id": str(organization_id)},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def recruiter_headers() -> dict[str, str]:
    """Authenticate the Alpha recruiter."""

    return auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID)


@pytest.fixture
def manager_headers() -> dict[str, str]:
    """Authenticate the Alpha hiring manager."""

    return auth_header("provider-alpha-manager", ALPHA_ORGANIZATION_ID)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Authenticate the Alpha administrator."""

    return auth_header("provider-alpha-admin", ALPHA_ORGANIZATION_ID)


@pytest.fixture
def beacon_headers() -> dict[str, str]:
    """Authenticate a hiring manager from the isolated Beacon tenant."""

    return auth_header("provider-beacon-manager", BEACON_ORGANIZATION_ID)


def role_payload(**overrides: object) -> dict[str, object]:
    """Build valid role input and apply focused test overrides."""

    payload: dict[str, object] = {
        "title": "Platform Engineer",
        "department": "Engineering",
        "location": "Remote",
        "job_description": JOB_DESCRIPTION,
    }
    payload.update(overrides)
    return payload


def construct_payload(*, autonomy_rating: int = 3) -> list[dict[str, object]]:
    """Build one valid, source-grounded rating for every construct."""

    return [
        {
            "key": key.value,
            "rating": autonomy_rating if key is ConstructKey.AUTONOMY else 3,
            "confidence": "medium",
            "rationale": f"Reviewed rationale for {key.value}.",
            "evidence": [EVIDENCE[key]],
        }
        for key in CONSTRUCT_KEYS
    ]


async def create_test_role(
    client: AsyncClient,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Create a role and assert the common successful response contract."""

    response = await client.post("/v1/roles", headers=headers, json=role_payload())
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


async def create_test_profile(
    client: AsyncClient,
    role_id: str,
    headers: dict[str, str],
    *,
    autonomy_rating: int = 3,
) -> dict[str, Any]:
    """Create a complete role-profile draft and return its response."""

    response = await client.post(
        f"/v1/roles/{role_id}/profiles",
        headers=headers,
        json={"constructs": construct_payload(autonomy_rating=autonomy_rating)},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


@pytest.mark.anyio
async def test_role_crud_enforces_rbac_tenant_isolation_and_archiving(
    role_client: AsyncClient,
    recruiter_headers: dict[str, str],
    manager_headers: dict[str, str],
    admin_headers: dict[str, str],
    beacon_headers: dict[str, str],
    role_session_factory: sessionmaker[Session],
) -> None:
    """Role operations enforce explicit roles, tenant boundaries, and soft deletion."""

    unauthenticated = await role_client.get("/v1/roles")
    manager_create = await role_client.post(
        "/v1/roles", headers=manager_headers, json=role_payload()
    )
    assert unauthenticated.status_code == 401
    assert manager_create.status_code == 403

    created = await create_test_role(role_client, recruiter_headers)
    role_id = created["id"]
    assert created["status"] == "draft"
    assert created["organization_id"] == str(ALPHA_ORGANIZATION_ID)

    alpha_list = await role_client.get("/v1/roles", headers=manager_headers)
    beacon_list = await role_client.get("/v1/roles", headers=beacon_headers)
    assert role_id in {role["id"] for role in alpha_list.json()}
    assert role_id not in {role["id"] for role in beacon_list.json()}

    own_read = await role_client.get(f"/v1/roles/{role_id}", headers=manager_headers)
    foreign_read = await role_client.get(f"/v1/roles/{role_id}", headers=beacon_headers)
    unknown_read = await role_client.get(f"/v1/roles/{UNKNOWN_ID}", headers=manager_headers)
    assert own_read.status_code == 200
    assert foreign_read.status_code == unknown_read.status_code == 404
    assert foreign_read.json()["code"] == unknown_read.json()["code"] == "resource_not_found"
    assert foreign_read.json()["detail"] == unknown_read.json()["detail"]

    updated = await role_client.patch(
        f"/v1/roles/{role_id}",
        headers=admin_headers,
        json={
            "title": "Senior Platform Engineer",
            "job_description": f"{JOB_DESCRIPTION} Additional context.",
        },
    )
    empty_patch = await role_client.patch(
        f"/v1/roles/{role_id}", headers=recruiter_headers, json={}
    )
    null_patch = await role_client.patch(
        f"/v1/roles/{role_id}", headers=recruiter_headers, json={"location": None}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Senior Platform Engineer"
    assert updated.json()["job_description"].endswith("Additional context.")
    assert empty_patch.status_code == null_patch.status_code == 422
    assert empty_patch.headers["content-type"].startswith("application/problem+json")
    assert empty_patch.json()["code"] == "request_validation_failed"
    assert empty_patch.json()["errors"][0]["pointer"] == ""

    archived = await role_client.delete(f"/v1/roles/{role_id}", headers=recruiter_headers)
    assert archived.status_code == 204
    archived_read = await role_client.get(f"/v1/roles/{role_id}", headers=manager_headers)
    archived_update = await role_client.patch(
        f"/v1/roles/{role_id}", headers=recruiter_headers, json={"title": "No change"}
    )
    archived_profile = await role_client.post(
        f"/v1/roles/{role_id}/profiles",
        headers=recruiter_headers,
        json={"constructs": construct_payload()},
    )
    assert archived_read.json()["status"] == "archived"
    assert archived_update.status_code == archived_profile.status_code == 409
    assert archived_update.json()["code"] == "role_archived"

    with role_session_factory() as session:
        create_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "role.created",
                AuditEvent.entity_id == UUID(role_id),
            )
        )
        assert create_event is not None
        assert create_event.organization_id == ALPHA_ORGANIZATION_ID


@pytest.mark.anyio
async def test_profile_edits_create_versions_and_hiring_manager_approval_is_immutable(
    role_client: AsyncClient,
    recruiter_headers: dict[str, str],
    manager_headers: dict[str, str],
    admin_headers: dict[str, str],
    role_session_factory: sessionmaker[Session],
) -> None:
    """Draft edits copy snapshots; only managers approve; approved content stays frozen."""

    role = await create_test_role(role_client, recruiter_headers)
    first = await create_test_profile(role_client, role["id"], recruiter_headers)
    assert first["version"] == 1
    assert first["status"] == "draft"

    revised_rating = deepcopy(construct_payload()[0])
    revised_rating["rating"] = 5
    revised = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{first['id']}",
        headers=recruiter_headers,
        json={"constructs": [revised_rating]},
    )
    assert revised.status_code == 200
    second = revised.json()
    assert second["id"] != first["id"]
    assert second["version"] == 2
    assert second["constructs"][0]["rating"] == 5
    assert len(second["constructs"]) == 6

    history = await role_client.get(f"/v1/roles/{role['id']}/profiles", headers=manager_headers)
    assert [profile["version"] for profile in history.json()] == [1, 2]

    old_snapshot = await role_client.get(
        f"/v1/roles/{role['id']}/profiles/{first['id']}", headers=manager_headers
    )
    assert old_snapshot.json()["status"] == "superseded"
    assert old_snapshot.json()["constructs"][0]["rating"] == 3

    recruiter_approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{second['id']}/approve",
        headers=recruiter_headers,
    )
    admin_approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{second['id']}/approve",
        headers=admin_headers,
    )
    assert recruiter_approval.status_code == admin_approval.status_code == 403

    approved = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{second['id']}/approve",
        headers=manager_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == str(ALPHA_MANAGER_ID)
    assert approved.json()["approved_at"] is not None

    role_read = await role_client.get(f"/v1/roles/{role['id']}", headers=manager_headers)
    approved_edit = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{second['id']}",
        headers=recruiter_headers,
        json={"constructs": [revised_rating]},
    )
    repeated_approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{second['id']}/approve",
        headers=manager_headers,
    )
    locked_description = await role_client.patch(
        f"/v1/roles/{role['id']}",
        headers=recruiter_headers,
        json={"job_description": f"{JOB_DESCRIPTION} Material change."},
    )
    assert role_read.json()["status"] == "active"
    assert approved_edit.status_code == repeated_approval.status_code == 409
    assert approved_edit.json()["code"] == "profile_not_editable"
    assert locked_description.json()["code"] == "job_description_locked"

    third = await create_test_profile(role_client, role["id"], recruiter_headers, autonomy_rating=4)
    third_approved = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{third['id']}/approve",
        headers=manager_headers,
    )
    assert third["version"] == 3
    assert third_approved.status_code == 200
    prior = await role_client.get(
        f"/v1/roles/{role['id']}/profiles/{second['id']}", headers=manager_headers
    )
    assert prior.json()["status"] == "superseded"

    with role_session_factory() as session:
        old_rating = session.get(
            RoleConstructRating,
            (UUID(first["id"]), ConstructKey.AUTONOMY),
        )
        assert old_rating is not None
        assert old_rating.rating == 3
        version_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "role_profile.version_created",
                AuditEvent.entity_id == UUID(second["id"]),
            )
        )
        assert version_event is not None


@pytest.mark.anyio
async def test_profile_validation_and_route_identity_checks(
    role_client: AsyncClient,
    recruiter_headers: dict[str, str],
    manager_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    """Profiles require complete grounded ratings and matching nested route IDs."""

    role = await create_test_role(role_client, recruiter_headers)
    ratings = construct_payload()
    missing = await role_client.post(
        f"/v1/roles/{role['id']}/profiles",
        headers=recruiter_headers,
        json={"constructs": ratings[:-1]},
    )
    duplicated = deepcopy(ratings)
    duplicated[-1] = deepcopy(duplicated[0])
    duplicate = await role_client.post(
        f"/v1/roles/{role['id']}/profiles",
        headers=recruiter_headers,
        json={"constructs": duplicated},
    )
    invalid_rating = deepcopy(ratings)
    invalid_rating[0]["rating"] = 6
    out_of_range = await role_client.post(
        f"/v1/roles/{role['id']}/profiles",
        headers=recruiter_headers,
        json={"constructs": invalid_rating},
    )
    ungrounded = deepcopy(ratings)
    ungrounded[0]["evidence"] = ["This sentence is absent."]
    bad_evidence = await role_client.post(
        f"/v1/roles/{role['id']}/profiles",
        headers=recruiter_headers,
        json={"constructs": ungrounded},
    )
    assert missing.status_code == duplicate.status_code == out_of_range.status_code == 422
    assert bad_evidence.status_code == 422
    assert bad_evidence.json()["code"] == "evidence_not_in_job_description"

    profile = await create_test_profile(role_client, role["id"], recruiter_headers)
    manager_create = await role_client.post(
        f"/v1/roles/{role['id']}/profiles",
        headers=manager_headers,
        json={"constructs": ratings},
    )
    duplicate_updates = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{profile['id']}",
        headers=recruiter_headers,
        json={"constructs": [ratings[0], ratings[0]]},
    )
    empty_updates = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{profile['id']}",
        headers=recruiter_headers,
        json={"constructs": []},
    )
    wrong_role = await role_client.get(
        f"/v1/roles/{ALPHA_ROLE_ID}/profiles/{profile['id']}", headers=manager_headers
    )
    foreign_read = await role_client.get(
        f"/v1/roles/{role['id']}/profiles/{profile['id']}", headers=beacon_headers
    )
    foreign_history = await role_client.get(
        f"/v1/roles/{role['id']}/profiles", headers=beacon_headers
    )
    foreign_approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{profile['id']}/approve",
        headers=beacon_headers,
    )
    missing_revision = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{UNKNOWN_ID}",
        headers=recruiter_headers,
        json={"constructs": [ratings[0]]},
    )
    assert manager_create.status_code == 403
    assert duplicate_updates.status_code == empty_updates.status_code == 422
    assert (
        wrong_role.status_code
        == foreign_read.status_code
        == foreign_history.status_code
        == foreign_approval.status_code
        == missing_revision.status_code
        == 404
    )


@pytest.mark.anyio
async def test_only_latest_draft_can_be_revised_or_approved(
    role_client: AsyncClient,
    recruiter_headers: dict[str, str],
    manager_headers: dict[str, str],
    role_session_factory: sessionmaker[Session],
) -> None:
    """The latest-version gate protects against stale concurrent review links."""

    role = await create_test_role(role_client, recruiter_headers)
    first = await create_test_profile(role_client, role["id"], recruiter_headers)
    second = await create_test_profile(role_client, role["id"], recruiter_headers)
    assert second["version"] == 2

    # Simulate stale external state so the independent latest-version guard is
    # exercised even though normal creation supersedes an earlier open draft.
    with role_session_factory() as session:
        stale = session.get(RoleProfile, UUID(first["id"]))
        assert stale is not None
        stale.status = RoleProfileStatus.DRAFT
        session.commit()

    stale_revision = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{first['id']}",
        headers=recruiter_headers,
        json={"constructs": [construct_payload()[0]]},
    )
    stale_approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{first['id']}/approve",
        headers=manager_headers,
    )
    assert stale_revision.status_code == stale_approval.status_code == 409
    assert stale_revision.json()["code"] == stale_approval.json()["code"] == ("profile_not_latest")


@pytest.mark.anyio
async def test_unknown_and_archived_resources_reject_profile_writes(
    role_client: AsyncClient,
    recruiter_headers: dict[str, str],
    manager_headers: dict[str, str],
) -> None:
    """Missing nested resources and archived role approvals fail safely."""

    unknown_create = await role_client.post(
        f"/v1/roles/{UNKNOWN_ID}/profiles",
        headers=recruiter_headers,
        json={"constructs": construct_payload()},
    )
    unknown_profile = await role_client.get(
        f"/v1/roles/{UNKNOWN_ID}/profiles/{UNKNOWN_ID}", headers=manager_headers
    )
    assert unknown_create.status_code == unknown_profile.status_code == 404

    role = await create_test_role(role_client, recruiter_headers)
    profile = await create_test_profile(role_client, role["id"], recruiter_headers)
    archived = await role_client.delete(f"/v1/roles/{role['id']}", headers=recruiter_headers)
    approval = await role_client.post(
        f"/v1/roles/{role['id']}/profiles/{profile['id']}/approve",
        headers=manager_headers,
    )
    missing_revision = await role_client.patch(
        f"/v1/roles/{role['id']}/profiles/{UNKNOWN_ID}",
        headers=recruiter_headers,
        json={"constructs": [construct_payload()[0]]},
    )
    assert archived.status_code == 204
    assert approval.status_code == missing_revision.status_code == 409
    assert approval.json()["code"] == missing_revision.json()["code"] == "role_archived"
