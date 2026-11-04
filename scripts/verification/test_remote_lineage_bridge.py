"""Owned-container, rollback-only evidence; no deployed database access."""

import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
import sqlalchemy as sa

spec = importlib.util.spec_from_file_location(
    "bridge", Path(__file__).with_name("remote_lineage_bridge.py")
)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


@pytest.fixture(scope="module")
def engine():
    b.guard()
    b.command("docker", "image", "inspect", "postgres:16")
    name = "iopsych-bridge-" + uuid4().hex[:12]
    container = b.command(
        "docker",
        "run",
        "--pull=never",
        "-d",
        "--name",
        name,
        "--label",
        "iopsych.owner=remote-lineage-bridge",
        "--label",
        "iopsych.synthetic=true",
        "-p",
        "127.0.0.1:5619:5432",
        "-e",
        "POSTGRES_USER=bridge",
        "-e",
        "POSTGRES_PASSWORD=synthetic-only",
        "-e",
        "POSTGRES_DB=iopsych_bridge",
        "postgres:16",
    ).strip()
    try:
        engine = sa.create_engine(b.URL)
        for _ in range(40):
            try:
                with engine.connect():
                    break
            except sa.exc.OperationalError:
                time.sleep(0.25)
        else:
            raise RuntimeError("Owned PostgreSQL did not become ready")
        yield engine
        engine.dispose()
    finally:
        b.command("docker", "rm", "-f", "-v", container)


def insert(c, table_name, **values):
    table = sa.Table(table_name, sa.MetaData(), autoload_with=c)
    if "id" in table.c:
        values.setdefault(
            "id",
            uuid5(
                NAMESPACE_URL,
                table_name + json.dumps(values, default=str, sort_keys=True),
            ),
        )
    if "created_at" in table.c:
        values.setdefault("created_at", datetime(2026, 11, 4, tzinfo=timezone.utc))
    c.execute(table.insert().values(**values))
    return values.get("id")


def populate(c, head):
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    legacy = json.loads(
        (b.ROOT / "apps/api/alembic/definitions/legacy-v1.json").read_text()
    )
    statuses = [
        "queued",
        "retrying",
        "sent",
        "delivered",
        "failed",
        "bounced",
        "complained",
        "reissue_required",
        "cancelled",
    ]
    request_ids = [
        uuid5(NAMESPACE_URL, "bridge-request-" + status) for status in statuses
    ]
    for tenant in range(2):
        org = insert(c, "organizations", slug=f"synthetic-{tenant}", name="Synthetic")
        user = insert(
            c,
            "users",
            organization_id=org,
            email="shared@example.invalid",
            name="Synthetic",
            role="admin",
            auth_subject=f"synthetic|{tenant}",
            is_active=not tenant,
        )
        role = insert(
            c,
            "roles",
            organization_id=org,
            title="Synthetic",
            department="Synthetic",
            location="Synthetic",
            job_description="Synthetic",
            status="draft",
        )
        profile = insert(
            c,
            "role_profiles",
            role_id=role,
            version=1,
            status="draft",
            created_by=user,
            assumptions_json={},
        )
        old = None
        for i, status in enumerate(statuses):
            invite = insert(
                c,
                "assessment_invites",
                role_profile_id=profile,
                email="candidate@example.invalid",
                token_hash=f"{tenant}{i}".ljust(64, "0"),
                expires_at=now,
                status="consented" if i < 3 else "active",
            )
            if i < 3:
                consent = insert(
                    c,
                    "candidate_consents",
                    invite_id=invite,
                    decision="consent",
                    notice_version="old-notice",
                )
                assessment = insert(
                    c,
                    "assessments",
                    invite_id=invite,
                    consent_id=consent,
                    submitted_at=now,
                    definition_json=legacy if i != 1 else {"unknown": True},
                    responses_json={"old": [1, 2]},
                    scores_json={"old": 3},
                    anonymized_at=now if i == 2 else None,
                )
                report = insert(
                    c,
                    "alignment_reports",
                    assessment_id=assessment,
                    role_profile_id=profile,
                    algorithm_version="1.0.0",
                    result_json={"old": "preserve exactly"},
                )
                insert(
                    c,
                    "alignment_items",
                    report_id=report,
                    construct_key="structure",
                    classification="old",
                    confidence="low",
                    explanation_json={"trace": "old"},
                    questions_json=["old"],
                )
            if head.endswith("0009"):
                delivery = insert(
                    c,
                    "invitation_deliveries",
                    organization_id=org,
                    invite_id=invite,
                    requested_by=user,
                    request_id=request_ids[i],
                    request_fingerprint="a" * 64,
                    replaces_invite_id=old,
                    encrypted_message="synthetic-ciphertext-" + str(i)
                    if i < 2
                    else None,
                    status=status,
                    attempt_count=i,
                    next_attempt_at=now,
                    retry_until=now,
                    provider_message_id=f"synthetic-{tenant}-{i}",
                )
                insert(
                    c,
                    "invitation_delivery_events",
                    provider_event_id=f"event-{tenant}-{i}",
                    delivery_id=delivery,
                    event_type=status,
                    occurred_at=now,
                )
            old = invite


def verify_preservation(c):
    legacy = json.loads(
        (b.ROOT / "apps/api/alembic/definitions/legacy-v1.json").read_text()
    )
    expected = {
        "contract_version": 1,
        "definition": legacy,
        "definition_sha256": b.digest(legacy),
        "matching_algorithm_version": "1.0.0",
    }
    assignments = c.execute(
        sa.text(
            "SELECT i.id,i.assignment_json,a.definition_json,a.anonymized_at FROM assessment_invites i LEFT JOIN assessments a ON a.invite_id=i.id"
        )
    ).all()
    for invite, assignment, definition, anonymized in assignments:
        assert assignment == (
            None
            if anonymized or (definition is not None and definition != legacy)
            else expected
        )
        with c.begin_nested() as tx:
            with pytest.raises(sa.exc.DBAPIError, match="assignments are immutable"):
                c.execute(
                    sa.text(
                        "UPDATE assessment_invites SET assignment_json = CAST(:value AS json) WHERE id=:id"
                    ),
                    {"id": invite, "value": '{"changed":true}'},
                )
            tx.rollback()
    assert c.scalar(sa.text("SELECT count(*) FROM users WHERE version=1")) == 2
    assert c.scalar(sa.text("SELECT count(*) FROM users WHERE is_active=false")) == 1
    assert c.scalar(sa.text("SELECT count(*) FROM invitation_deliveries")) == 0
    assert (
        c.scalar(
            sa.text(
                "SELECT count(*) FROM assessment_invites WHERE notice_snapshot_json IS NOT NULL OR notice_sha256 IS NOT NULL OR notice_snapshot_origin IS NOT NULL OR notice_snapshot_recorded_at IS NOT NULL"
            )
        )
        == 0
    )
    assert (
        c.scalar(
            sa.text(
                "SELECT count(*) FROM candidate_consents WHERE presented_notice_sha256 IS NOT NULL"
            )
        )
        == 0
    )
    with c.begin_nested() as tx:
        with pytest.raises(sa.exc.IntegrityError):
            c.execute(
                sa.text(
                    "UPDATE users SET auth_subject='synthetic|0' WHERE auth_subject='synthetic|1'"
                )
            )
        tx.rollback()
    if c.scalar(sa.text("SELECT count(*) FROM provider_invitation_delivery_events")):
        with c.begin_nested() as tx:
            with pytest.raises(sa.exc.IntegrityError):
                c.execute(
                    sa.text(
                        "INSERT INTO provider_invitation_delivery_events SELECT * FROM provider_invitation_delivery_events LIMIT 1"
                    )
                )
            tx.rollback()


@pytest.mark.parametrize("head", ["20261103_0008", "20261103_0009"])
def test_populated_rollback_experiment(engine, head, capsys):
    with engine.connect() as c:
        with c.begin() as tx:
            b.create_lineage(c, "canonical")
            target = b.signature(c)
            tx.rollback()
        with c.begin():
            b.create_lineage(c, head)
            source = b.signature(c)
            populate(c, head)
            before = b.rows(c)[1]
            receipt = b.experiment(c, source, target, verify=verify_preservation)
            assert receipt["version_translated"] is False
            assert b.signature(c) == source
            assert b.rows(c)[1] == before
            assert c.scalar(sa.text("SELECT version_num FROM alembic_version")) == head
            assert b.experiment(c, source, target) == receipt
            with pytest.raises(RuntimeError, match="Injected"):
                b.experiment(c, source, target, inject=True)
            assert b.signature(c) == source
            assert b.rows(c)[1] == before
            with c.begin_nested() as tx:
                c.execute(sa.text("ALTER TABLE users ADD COLUMN unexpected integer"))
                with pytest.raises(RuntimeError, match="Unknown source schema"):
                    b.experiment(c, source, target)
                tx.rollback()
            with c.begin_nested() as tx:
                c.execute(sa.text("UPDATE alembic_version SET version_num='unknown'"))
                with pytest.raises(RuntimeError, match="Unknown source revision"):
                    b.experiment(c, source, target)
                tx.rollback()
            print(json.dumps(receipt, sort_keys=True))
            c.rollback()
    captured = capsys.readouterr()
    print(captured.out)


def test_cli_is_blocked():
    with pytest.raises(SystemExit, match="operational bridge is not implemented"):
        b.main()


def test_wrong_database_is_refused():
    with (
        sa.create_engine("sqlite://").connect() as c,
        pytest.raises(RuntimeError, match="Only the isolated"),
    ):
        b.experiment(c, {}, {})


def test_remote_provenance_mismatch_is_refused(monkeypatch):
    name = next(iter(b.SOURCES))
    monkeypatch.setitem(b.SOURCES, name, "0" * 64)
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        b.source_bytes(name)
