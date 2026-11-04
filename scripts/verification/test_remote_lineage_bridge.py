"""Owned-container, rollback-only evidence; no deployed database access."""

import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
import sqlalchemy as sa

spec = importlib.util.spec_from_file_location(
    "bridge", Path(__file__).with_name("remote_lineage_bridge.py")
)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


@pytest.fixture(scope="module")
def engine():
    bridge.guard()
    bridge.command("docker", "image", "inspect", "postgres:16")
    name = "iopsych-bridge-" + uuid4().hex[:12]
    container = bridge.command(
        "docker",
        "create",
        "--pull=never",
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
    engine = None
    try:
        bridge.command("docker", "start", container)
        engine = sa.create_engine(bridge.URL)
        for _ in range(40):
            try:
                with engine.connect():
                    break
            except sa.exc.OperationalError:
                time.sleep(0.25)
        else:
            raise RuntimeError("Owned PostgreSQL did not become ready")
        yield engine
    finally:
        try:
            if engine is not None:
                engine.dispose()
        finally:
            bridge.command("docker", "rm", "-f", "-v", container)


def insert(connection, table_name, **values):
    table = sa.Table(table_name, sa.MetaData(), autoload_with=connection)
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
    connection.execute(table.insert().values(**values))
    return values.get("id")


def populate(connection, head):
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    legacy = json.loads(
        (bridge.ROOT / "apps/api/alembic/definitions/legacy-v1.json").read_text()
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
        org = insert(
            connection, "organizations", slug=f"synthetic-{tenant}", name="Synthetic"
        )
        user = insert(
            connection,
            "users",
            organization_id=org,
            email="shared@example.invalid",
            name="Synthetic",
            role="admin",
            auth_subject=f"synthetic|{tenant}",
            is_active=not tenant,
        )
        role = insert(
            connection,
            "roles",
            organization_id=org,
            title="Synthetic",
            department="Synthetic",
            location="Synthetic",
            job_description="Synthetic",
            status="draft",
        )
        profile = insert(
            connection,
            "role_profiles",
            role_id=role,
            version=1,
            status="draft",
            created_by=user,
            assumptions_json={},
        )
        old = None
        for status_index, status in enumerate(statuses):
            invite = insert(
                connection,
                "assessment_invites",
                role_profile_id=profile,
                email="candidate@example.invalid",
                token_hash=f"{tenant}{status_index}".ljust(64, "0"),
                expires_at=now,
                status="consented" if status_index < 3 else "active",
            )
            if status_index < 3:
                consent = insert(
                    connection,
                    "candidate_consents",
                    invite_id=invite,
                    decision="consent",
                    notice_version="old-notice",
                )
                assessment = insert(
                    connection,
                    "assessments",
                    invite_id=invite,
                    consent_id=consent,
                    submitted_at=now,
                    definition_json=legacy if status_index != 1 else {"unknown": True},
                    responses_json={"old": [1, 2]},
                    scores_json={"old": 3},
                    anonymized_at=now if status_index == 2 else None,
                )
                report = insert(
                    connection,
                    "alignment_reports",
                    assessment_id=assessment,
                    role_profile_id=profile,
                    algorithm_version="1.0.0",
                    result_json={"old": "preserve exactly"},
                )
                insert(
                    connection,
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
                    connection,
                    "invitation_deliveries",
                    organization_id=org,
                    invite_id=invite,
                    requested_by=user,
                    request_id=request_ids[status_index],
                    request_fingerprint="a" * 64,
                    replaces_invite_id=old,
                    encrypted_message="synthetic-ciphertext-" + str(status_index)
                    if status_index < 2
                    else None,
                    status=status,
                    attempt_count=status_index,
                    next_attempt_at=now,
                    retry_until=now,
                    provider_message_id=f"synthetic-{tenant}-{status_index}",
                )
                insert(
                    connection,
                    "invitation_delivery_events",
                    provider_event_id=f"event-{tenant}-{status_index}",
                    delivery_id=delivery,
                    event_type=status,
                    occurred_at=now,
                )
            old = invite


def verify_preservation(connection):
    legacy = json.loads(
        (bridge.ROOT / "apps/api/alembic/definitions/legacy-v1.json").read_text()
    )
    expected = {
        "contract_version": 1,
        "definition": legacy,
        "definition_sha256": bridge.digest(legacy),
        "matching_algorithm_version": "1.0.0",
    }
    assignments = connection.execute(
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
        with connection.begin_nested() as tx:
            with pytest.raises(sa.exc.DBAPIError, match="assignments are immutable"):
                connection.execute(
                    sa.text(
                        "UPDATE assessment_invites SET assignment_json = CAST(:value AS json) WHERE id=:id"
                    ),
                    {"id": invite, "value": '{"changed":true}'},
                )
            tx.rollback()
    assert connection.scalar(sa.text("SELECT count(*) FROM users WHERE version=1")) == 2
    assert (
        connection.scalar(sa.text("SELECT count(*) FROM users WHERE is_active=false"))
        == 1
    )
    assert connection.scalar(sa.text("SELECT count(*) FROM invitation_deliveries")) == 0
    assert (
        connection.scalar(
            sa.text(
                "SELECT count(*) FROM assessment_invites WHERE notice_snapshot_json IS NOT NULL OR notice_sha256 IS NOT NULL OR notice_snapshot_origin IS NOT NULL OR notice_snapshot_recorded_at IS NOT NULL"
            )
        )
        == 0
    )
    assert (
        connection.scalar(
            sa.text(
                "SELECT count(*) FROM candidate_consents WHERE presented_notice_sha256 IS NOT NULL"
            )
        )
        == 0
    )
    with connection.begin_nested() as tx:
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "UPDATE users SET auth_subject='synthetic|0' WHERE auth_subject='synthetic|1'"
                )
            )
        tx.rollback()
    if connection.scalar(
        sa.text("SELECT count(*) FROM provider_invitation_delivery_events")
    ):
        with connection.begin_nested() as tx:
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO provider_invitation_delivery_events SELECT * FROM provider_invitation_delivery_events LIMIT 1"
                    )
                )
            tx.rollback()


@pytest.mark.parametrize("head", ["20261103_0008", "20261103_0009"])
def test_populated_rollback_experiment(engine, head, capsys):
    with engine.connect() as connection:
        with connection.begin() as tx:
            bridge.create_lineage(connection, "canonical")
            target = bridge.signature(connection)
            tx.rollback()
        with connection.begin():
            bridge.create_lineage(connection, head)
            source = bridge.signature(connection)
            populate(connection, head)
            before = bridge.rows(connection)[1]
            receipt = bridge.experiment(
                connection, source, target, verify=verify_preservation
            )
            assert receipt["version_translated"] is False
            assert bridge.signature(connection) == source
            assert bridge.rows(connection)[1] == before
            assert (
                connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
                == head
            )
            assert bridge.experiment(connection, source, target) == receipt
            with pytest.raises(RuntimeError, match="Injected"):
                bridge.experiment(connection, source, target, inject=True)
            assert bridge.signature(connection) == source
            assert bridge.rows(connection)[1] == before
            with connection.begin_nested() as tx:
                connection.execute(
                    sa.text("ALTER TABLE users ADD COLUMN unexpected integer")
                )
                with pytest.raises(RuntimeError, match="Unknown source schema"):
                    bridge.experiment(connection, source, target)
                tx.rollback()
            with connection.begin_nested() as tx:
                connection.execute(
                    sa.text("UPDATE alembic_version SET version_num='unknown'")
                )
                with pytest.raises(RuntimeError, match="Unknown source revision"):
                    bridge.experiment(connection, source, target)
                tx.rollback()
            print(json.dumps(receipt, sort_keys=True))
            connection.rollback()
    captured = capsys.readouterr()
    print(captured.out)


def test_cli_is_blocked():
    with pytest.raises(SystemExit, match="operational bridge is not implemented"):
        bridge.main()


def test_wrong_database_is_refused():
    with (
        sa.create_engine("sqlite://").connect() as connection,
        pytest.raises(RuntimeError, match="Only the isolated"),
    ):
        bridge.experiment(connection, {}, {})


def test_remote_provenance_mismatch_is_refused(monkeypatch):
    name = next(iter(bridge.SOURCES))
    monkeypatch.setitem(bridge.SOURCES, name, "0" * 64)
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        bridge.source_bytes(name)


@pytest.mark.parametrize(
    "variable",
    [
        "PGHOSTADDR",
        "PGOPTIONS",
        "PGSERVICE",
        "DATABASE_URL",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
    ],
)
def test_ambient_configuration_is_refused(monkeypatch, variable):
    monkeypatch.setenv(variable, "synthetic-invalid")
    with pytest.raises(RuntimeError, match="Unset ambient"):
        bridge.guard()


def test_remote_docker_endpoint_is_refused(monkeypatch):
    monkeypatch.setattr(bridge, "command", lambda *arguments: "tcp://127.0.0.1:2375")
    with pytest.raises(RuntimeError, match="local Unix-socket"):
        bridge.guard()


def test_occupied_port_is_refused(monkeypatch, engine):
    monkeypatch.setattr(
        bridge, "command", lambda *arguments: "unix:///synthetic/docker.sock"
    )
    with pytest.raises(OSError):
        bridge.guard()


def test_start_failure_removes_owned_container(monkeypatch):
    calls = []

    def command(*arguments):
        calls.append(arguments)
        if arguments[:2] == ("docker", "create"):
            return "synthetic-owned-container"
        if arguments[:2] == ("docker", "start"):
            raise RuntimeError("Synthetic start failure")
        return ""

    monkeypatch.setattr(bridge, "guard", lambda: None)
    monkeypatch.setattr(bridge, "command", command)
    with pytest.raises(RuntimeError, match="Synthetic start failure"):
        next(engine.__wrapped__())
    assert calls[-1] == ("docker", "rm", "-f", "-v", "synthetic-owned-container")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://bridge:synthetic-only@localhost:5619/iopsych_bridge",
        "postgresql+psycopg://bridge:synthetic-only@127.0.0.1:5432/iopsych_bridge",
        "postgresql+psycopg://bridge:synthetic-only@127.0.0.1:5619/iopsych_bridge?host=/tmp",
        "postgresql+psycopg://bridge:synthetic-only@127.0.0.1:5619/other",
    ],
)
def test_changed_connection_target_is_refused(url):
    connection = SimpleNamespace(engine=SimpleNamespace(url=sa.engine.make_url(url)))
    with pytest.raises(RuntimeError, match="Only the isolated"):
        bridge.experiment(connection, {}, {})
