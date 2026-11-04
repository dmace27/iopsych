"""Synthetic local deletion replay experiment, never a production recovery tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from local_restore_rehearsal import IMAGE, normalize_schema, require, run

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "iopsych-deletion-replay-rehearsal"
PORT = 5601


def guard(project, environment, root=ROOT):
    require(project == PROJECT, "explicit own-project acknowledgement required")
    require(
        not any(
            key.startswith("PG")
            or key
            in {"DATABASE_URL", "TEST_POSTGRES_URL", "DOCKER_HOST", "DOCKER_CONTEXT"}
            for key in environment
        ),
        "unset ambient database/Docker target variables; values are never printed",
    )
    require(
        not any((root / path).exists() for path in (".env", "apps/api/.env")),
        ".env must be absent in this isolated checkout",
    )


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def validate_journal(raw, digest, run_id, snapshot_digest):
    require(hashlib.sha256(raw).hexdigest() == digest, "journal integrity mismatch")
    payload = json.loads(raw)
    require(
        isinstance(payload, dict)
        and set(payload) == {"version", "run_id", "snapshot_sha256", "entries"},
        "invalid journal envelope",
    )
    require(
        type(payload["version"]) is int and payload["version"] == 1,
        "unknown journal version",
    )
    require(payload["run_id"] == run_id, "journal run mismatch")
    require(payload["snapshot_sha256"] == snapshot_digest, "journal snapshot mismatch")
    require(
        isinstance(payload["entries"], list) and len(payload["entries"]) == 1,
        "expected one synthetic tombstone",
    )
    entry = payload["entries"][0]
    require(
        isinstance(entry, dict)
        and set(entry) == {"tenant_id", "assessment_id", "deleted_at"},
        "invalid tombstone fields",
    )
    UUID(entry["tenant_id"])
    UUID(entry["assessment_id"])
    stamp = datetime.fromisoformat(entry["deleted_at"])
    require(stamp.utcoffset() == timedelta(0), "deletion timestamp must be UTC")
    return entry


def replay(session, entry, actor_id):
    from app.auth.context import AuthorizationContext, OrganizationScope
    from app.auth.dependencies import require_roles
    from app.database.models import InternalUserRole, User
    from app.privacy.config import PrivacySettings
    from app.privacy.service import PrivacyService

    actor = session.get(User, actor_id, populate_existing=True)
    require(actor is not None and actor.is_active, "active synthetic actor required")
    context = AuthorizationContext(
        actor.id,
        OrganizationScope(actor.organization_id),
        actor.email,
        actor.name,
        actor.role,
    )
    require_roles(InternalUserRole.ADMIN)(context)
    context.organization.require_matches(UUID(entry["tenant_id"]))
    return PrivacyService(session, PrivacySettings(_env_file=None), context).anonymize(
        UUID(entry["assessment_id"]), now=datetime.fromisoformat(entry["deleted_at"])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    args = parser.parse_args()
    guard(args.project, os.environ)
    endpoint = (
        run(
            "docker",
            "context",
            "inspect",
            "desktop-linux",
            "--format",
            "{{.Endpoints.docker.Host}}",
        )
        .decode()
        .strip()
    )
    require(
        endpoint.startswith("unix:///"), "Docker Desktop must use a local Unix socket"
    )
    docker = ["docker", "--host", endpoint]
    run(*docker, "image", "inspect", IMAGE)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", PORT))
    sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/shared/python")]
    from alembic import command
    from alembic.config import Config
    from app.auth.errors import AccessProblemError
    from app.database.models import (
        AlignmentReport,
        AlignmentReportItem,
        Assessment,
        AssessmentInvite,
        AssessmentInviteStatus,
        AuditEvent,
        CandidateConsent,
        ConsentDecision,
        InternalUserRole,
        User,
    )
    from app.database.seed import (
        ALPHA_ORGANIZATION_ID,
        ALPHA_PROFILE_ID,
        ALPHA_USER_ID,
        BEACON_ORGANIZATION_ID,
        BEACON_USER_ID,
        seed_database,
    )
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    identity = f"{PROJECT}-{uuid4().hex}"
    cid = None
    engines = []

    def sql(db, statement):
        return (
            run(
                *docker,
                "exec",
                cid,
                "psql",
                "-X",
                "-U",
                "rehearsal",
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                statement,
            )
            .decode()
            .strip()
        )

    def schema(db):
        return normalize_schema(
            run(
                *docker,
                "exec",
                cid,
                "pg_dump",
                "-U",
                "rehearsal",
                "-d",
                db,
                "--schema-only",
                "--no-owner",
                "--no-privileges",
            ).decode()
        )

    def connect(db):
        engine = create_engine(
            f"postgresql+psycopg://rehearsal:synthetic-local-only@127.0.0.1:{PORT}/{db}"
        )
        engines.append(engine)
        return engine

    def state(db, assessment_id):
        return sql(
            db,
            f"SELECT row_to_json(a)::text || row_to_json(i)::text || row_to_json(r)::text || row_to_json(ri)::text FROM assessments a JOIN assessment_invites i ON i.id=a.invite_id JOIN alignment_reports r ON r.assessment_id=a.id JOIN alignment_items ri ON ri.report_id=r.id WHERE a.id='{assessment_id}'",
        )

    try:
        cid = (
            run(
                *docker,
                "run",
                "--detach",
                "--pull=never",
                "--name",
                identity,
                "--label",
                f"rehearsal.owner={identity}",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
                "--tmpfs",
                "/rehearsal:rw,noexec,nosuid,size=128m",
                "--publish",
                f"127.0.0.1:{PORT}:5432",
                "--env",
                "POSTGRES_USER=rehearsal",
                "--env",
                "POSTGRES_DB=source",
                "--env",
                "POSTGRES_PASSWORD=synthetic-local-only",
                IMAGE,
            )
            .decode()
            .strip()
        )
        for attempt in range(60):
            try:
                run(
                    *docker,
                    "exec",
                    cid,
                    "pg_isready",
                    "-U",
                    "rehearsal",
                    "-d",
                    "source",
                )
                break
            except subprocess.CalledProcessError:
                time.sleep(0.5)
        else:
            raise RuntimeError("owned PostgreSQL readiness timed out")
        source = connect("source")
        os.environ["DATABASE_URL"] = source.url.render_as_string(hide_password=False)
        command.upgrade(Config(str(ROOT / "apps/api/alembic.ini")), "head")
        with Session(source) as session:
            seed_database(session)
            session.get(User, ALPHA_USER_ID).role = InternalUserRole.ADMIN
            session.get(User, BEACON_USER_ID).role = InternalUserRole.ADMIN
            ids = []
            for label in ("deleted", "control"):
                invite = AssessmentInvite(
                    role_profile_id=ALPHA_PROFILE_ID,
                    email=f"{label}@example.invalid",
                    token_hash=hashlib.sha256(label.encode()).hexdigest(),
                    expires_at=datetime.now(UTC) + timedelta(days=1),
                    status=AssessmentInviteStatus.CONSENTED,
                )
                session.add(invite)
                session.flush()
                consent = CandidateConsent(
                    invite_id=invite.id,
                    decision=ConsentDecision.CONSENT,
                    notice_version="synthetic-replay",
                )
                session.add(consent)
                session.flush()
                assessment = Assessment(
                    invite_id=invite.id,
                    consent_id=consent.id,
                    submitted_at=datetime.now(UTC),
                    definition_json={"synthetic": label},
                    responses_json={"synthetic": label},
                    scores_json={"synthetic": label},
                )
                session.add(assessment)
                session.flush()
                report = AlignmentReport(
                    assessment_id=assessment.id,
                    role_profile_id=ALPHA_PROFILE_ID,
                    algorithm_version="synthetic-replay",
                    result_json={"synthetic": label},
                )
                session.add(report)
                session.flush()
                session.add(
                    AlignmentReportItem(
                        report_id=report.id,
                        construct_key="autonomy",
                        classification="aligned",
                        confidence="high",
                        explanation_json={"synthetic": label},
                        questions_json={"synthetic": label},
                    )
                )
                ids.append(assessment.id)
            session.commit()
        deleted, control = ids
        control_before = state("source", control)
        audit_before = sql(
            "source", "SELECT json_agg(a ORDER BY id)::text FROM audit_events a"
        )
        dump = run(
            *docker, "exec", cid, "pg_dump", "-U", "rehearsal", "-d", "source", "-Fc"
        )
        snapshot_digest = hashlib.sha256(dump).hexdigest()
        entry = {
            "tenant_id": str(ALPHA_ORGANIZATION_ID),
            "assessment_id": str(deleted),
            "deleted_at": datetime.now(UTC).isoformat(),
        }
        with Session(source) as session:
            result = replay(session, entry, ALPHA_USER_ID)
            require(
                result.reports_deleted == 1 and not result.already_anonymized,
                "source deletion failed",
            )
        raw = canonical(
            {
                "version": 1,
                "run_id": identity,
                "snapshot_sha256": snapshot_digest,
                "entries": [entry],
            }
        )
        digest = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(
            prefix="iopsych-synthetic-journal-"
        ) as directory:
            journal = Path(directory) / "deletions.json"
            with journal.open("xb") as handle:
                os.chmod(journal, 0o600)
                handle.write(raw)
            validate_journal(journal.read_bytes(), digest, identity, snapshot_digest)
            run(
                *docker,
                "exec",
                "-i",
                cid,
                "sh",
                "-c",
                "cat > /rehearsal/before.dump",
                data=dump,
            )
            require(
                hashlib.sha256(
                    run(*docker, "exec", cid, "cat", "/rehearsal/before.dump")
                ).hexdigest()
                == snapshot_digest,
                "snapshot transfer mismatch",
            )
            run(*docker, "exec", cid, "createdb", "-U", "rehearsal", "restored")
            run(
                *docker,
                "exec",
                cid,
                "pg_restore",
                "-U",
                "rehearsal",
                "-d",
                "restored",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "/rehearsal/before.dump",
            )
            require(schema("source") == schema("restored"), "restored schema mismatch")
            require(
                sql("source", "SELECT version_num FROM alembic_version")
                == sql("restored", "SELECT version_num FROM alembic_version"),
                "migration head mismatch",
            )
            require(
                bool(state("restored", deleted)),
                "pre-deletion data/report not restored",
            )
            require(
                sql(
                    "restored",
                    f"SELECT count(*) FROM assessments WHERE id='{deleted}' AND anonymized_at IS NULL",
                )
                == "1",
                "expected unsafe pre-replay state missing",
            )
            print(
                "PASS: verified pre-deletion snapshot restores candidate data and report; quarantined"
            )
            restored = connect("restored")
            restored_before = state("restored", deleted)
            require(
                sql(
                    "restored",
                    "SELECT json_agg(a ORDER BY id)::text FROM audit_events a",
                )
                == audit_before,
                "pre-deletion snapshot unexpectedly contains later audit",
            )
            entry = validate_journal(
                journal.read_bytes(), digest, identity, snapshot_digest
            )
            with Session(restored) as session:
                for bad_entry in (
                    entry,
                    {**entry, "tenant_id": str(BEACON_ORGANIZATION_ID)},
                ):
                    try:
                        replay(session, bad_entry, BEACON_USER_ID)
                    except AccessProblemError as error:
                        require(error.status == 404, "unexpected tenant rejection")
                        session.rollback()
                    else:
                        raise RuntimeError("cross-tenant replay accepted")
                actor = session.get(User, ALPHA_USER_ID)
                actor.role = InternalUserRole.RECRUITER
                session.flush()
                try:
                    replay(session, entry, ALPHA_USER_ID)
                except AccessProblemError as error:
                    require(error.status == 403, "unexpected role rejection")
                    session.rollback()
                else:
                    raise RuntimeError("non-admin replay accepted")
                require(
                    state("restored", deleted) == restored_before,
                    "denied replay changed candidate",
                )
                require(
                    sql(
                        "restored",
                        "SELECT json_agg(a ORDER BY id)::text FROM audit_events a",
                    )
                    == audit_before,
                    "denied replay changed audit",
                )
                result = replay(session, entry, ALPHA_USER_ID)
                require(
                    result.reports_deleted == 1 and not result.already_anonymized,
                    "replay deletion failed",
                )
                duplicate = replay(session, entry, ALPHA_USER_ID)
                require(
                    duplicate.already_anonymized
                    and duplicate.reports_deleted == 0
                    and duplicate.anonymized_at == result.anonymized_at,
                    "duplicate replay changed result",
                )
                assessment = session.get(Assessment, deleted)
                invite = session.get(AssessmentInvite, assessment.invite_id)
                require(
                    assessment.anonymized_at
                    == datetime.fromisoformat(entry["deleted_at"]),
                    "deletion timestamp not preserved",
                )
                require(
                    all(
                        value == {"anonymized": True}
                        for value in (
                            assessment.definition_json,
                            assessment.responses_json,
                            assessment.scores_json,
                        )
                    ),
                    "payload survived",
                )
                require(
                    invite.email == f"deleted-{invite.id.hex}@privacy.invalid"
                    and invite.token_hash != hashlib.sha256(b"deleted").hexdigest()
                    and invite.status == AssessmentInviteStatus.REVOKED
                    and invite.revoked_at == assessment.anonymized_at,
                    "invitation not erased/revoked",
                )
                events = list(
                    session.scalars(
                        select(AuditEvent).where(AuditEvent.entity_id == deleted)
                    )
                )
                require(
                    len(events) == 1
                    and events[0].actor_id == ALPHA_USER_ID
                    and events[0].organization_id == ALPHA_ORGANIZATION_ID
                    and events[0].event_type == "candidate_data.anonymized",
                    "audit tombstone mismatch",
                )
            require(
                sql(
                    "restored",
                    f"SELECT count(*) FROM alignment_reports WHERE assessment_id='{deleted}'",
                )
                == "0",
                "report survived",
            )
            require(
                sql("restored", "SELECT count(*) FROM alignment_items") == "1",
                "report item survived",
            )
            require(state("restored", control) == control_before, "control changed")
            require(
                sql(
                    "restored",
                    "SELECT json_agg(a ORDER BY id)::text FROM audit_events a WHERE event_type='seed.role_profile_created'",
                )
                == audit_before,
                "existing audit changed",
            )
            for statement in (
                "UPDATE audit_events SET event_type='synthetic-mutated'",
                "DELETE FROM audit_events",
            ):
                try:
                    sql("restored", statement)
                except subprocess.CalledProcessError as error:
                    require(
                        b"audit events are immutable" in error.stderr.lower(),
                        "unexpected audit rejection",
                    )
                else:
                    raise RuntimeError("audit mutation accepted")
            print(
                "PASS: external journal binding, tenant/role denial, authorized replay and duplicate idempotency"
            )
            print(
                "PASS: payload/email/token erasure, revoked invite, reports/items erased, control preserved"
            )
            print(
                "PASS: deletion timestamp/actor/tenant audit, prior audits preserved, UPDATE/DELETE rejected"
            )
        print(
            "LOCAL ONLY: no production journal durability, encryption, completeness or retention approval"
        )
    finally:
        for engine in engines:
            engine.dispose()
        os.environ.pop("DATABASE_URL", None)
        if cid is not None:
            owner = (
                run(
                    *docker,
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "rehearsal.owner"}}',
                    cid,
                )
                .decode()
                .strip()
            )
            require(owner == identity, "refusing non-owned cleanup")
            run(*docker, "rm", "--force", "--volumes", cid)
        print(
            "Cleanup: own container/tmpfs snapshots and temporary external journal removed"
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        print(
            "FAIL: local subprocess failed; payload/connection output suppressed",
            file=sys.stderr,
        )
        sys.exit(1)
    except (RuntimeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
