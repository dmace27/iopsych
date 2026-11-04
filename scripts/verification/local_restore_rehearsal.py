#!/usr/bin/env python3
"""Synthetic-only local PostgreSQL snapshot experiment; never a recovery tool."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "iopsych-restore-rehearsal"
PORT = 5585
IMAGE = "postgres:16-bookworm"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def guard(project, environment):
    require(project == PROJECT, "explicit own-project acknowledgement required")
    require(
        not any(
            k in environment
            for k in (
                "DATABASE_URL",
                "TEST_POSTGRES_URL",
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "PGHOST",
                "PGPORT",
                "PGDATABASE",
                "PGUSER",
                "PGPASSWORD",
                "PGSERVICE",
                "PGSERVICEFILE",
                "PGPASSFILE",
            )
        ),
        "unset ambient database/Docker target variables; values are never printed",
    )
    require(
        not (ROOT / "apps/api/.env").exists(),
        "API .env must be absent in this isolated checkout",
    )


def run(*args, data=None):
    return subprocess.run(
        args, input=data, capture_output=True, check=True, timeout=120
    ).stdout


def normalize_schema(result):
    """Normalize PostgreSQL's equivalent array-to-element text cast rewrite only."""
    result = re.sub(
        r"\(ARRAY\[((?:'[^']*'::character varying)(?:, '[^']*'::character varying)*)\]\)::text\[\]",
        lambda match: (
            "ARRAY["
            + ", ".join(f"({item})::text" for item in match[1].split(", "))
            + "]"
        ),
        result,
    )
    return "\n".join(
        line
        for line in result.splitlines()
        if line and not line.startswith(("--", "\\"))
    )


def self_test():
    for env in (
        {"DATABASE_URL": "redacted"},
        {"DOCKER_HOST": "redacted"},
        {"TEST_POSTGRES_URL": "redacted"},
        {"PGSERVICE": "redacted"},
    ):
        try:
            guard(PROJECT, env)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("unsafe environment accepted")
    try:
        guard("someone-elses-project", {})
    except RuntimeError:
        pass
    else:
        raise RuntimeError("foreign project accepted")
    guard(PROJECT, {})
    original = "CHECK (x = ANY ((ARRAY['a'::character varying, 'b'::character varying])::text[]))"
    restored = "CHECK (x = ANY (ARRAY[('a'::character varying)::text, ('b'::character varying)::text]))"
    require(
        normalize_schema(original) == normalize_schema(restored),
        "cast normalization failed",
    )
    require(
        normalize_schema(original) != normalize_schema(restored.replace("'b'", "'c'")),
        "changed constraint hidden",
    )
    print(
        "PASS: project and ambient-target guards and schema normalization (8 checks); no Docker mutation"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    guard(args.project, os.environ)
    # Explicit local socket, never an inherited remote context or URL.
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
    run(*docker, "image", "inspect", IMAGE)  # No pull/build/install fallback.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", PORT))  # Never stop a process to claim the port.
    sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "packages/shared/python")]
    from datetime import UTC, datetime, timedelta

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.database.models import (
        AlignmentReport,
        AlignmentReportItem,
        Assessment,
        AssessmentInvite,
        AssessmentInviteStatus,
        CandidateConsent,
        ConsentDecision,
    )
    from app.database.seed import ALPHA_PROFILE_ID, seed_database
    from app.privacy.config import PrivacySettings
    from app.privacy.service import PrivacyService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    identity = f"{PROJECT}-{uuid4().hex[:12]}"
    owned = []
    engine = None

    def start(suffix, publish=False):
        name = f"{identity}-{suffix}"
        options = (
            ["--publish", f"127.0.0.1:{PORT}:5432"]
            if publish
            else ["--network", "none"]
        )
        cid = (
            run(
                *docker,
                "run",
                "--detach",
                "--pull=never",
                "--name",
                name,
                "--label",
                f"rehearsal.owner={identity}",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
                "--tmpfs",
                "/rehearsal:rw,noexec,nosuid,size=128m",
                *options,
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
        owned.append(cid)
        for _ in range(60):
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
                return cid
            except subprocess.CalledProcessError:
                time.sleep(0.5)
        raise RuntimeError("owned PostgreSQL readiness timed out")

    def sql(cid, db, statement):
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

    def schema(cid, db):
        result = run(
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
        return normalize_schema(result)

    try:
        source = start("source", publish=True)
        target = start("restore")
        url = f"postgresql+psycopg://rehearsal:synthetic-local-only@127.0.0.1:{PORT}/source"
        os.environ["DATABASE_URL"] = (
            url  # Generated only after owning the fresh container.
        )
        config = Config(str(ROOT / "apps/api/alembic.ini"))
        command.upgrade(config, "head")
        head = ScriptDirectory.from_config(config).get_current_head()
        engine = create_engine(url)
        with Session(engine) as session:
            seed_database(session)
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
                    notice_version="synthetic-rehearsal",
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
                    algorithm_version="synthetic-rehearsal",
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

        def snapshot(name):
            dump = run(
                *docker,
                "exec",
                source,
                "pg_dump",
                "-U",
                "rehearsal",
                "-d",
                "source",
                "-Fc",
            )
            run(
                *docker,
                "exec",
                "-i",
                target,
                "sh",
                "-c",
                f"cat > /rehearsal/{name}.dump",
                data=dump,
            )
            copied = run(*docker, "exec", target, "cat", f"/rehearsal/{name}.dump")
            require(
                hashlib.sha256(dump).digest() == hashlib.sha256(copied).digest(),
                "dump copy mismatch",
            )
            run(*docker, "exec", target, "createdb", "-U", "rehearsal", name)
            run(
                *docker,
                "exec",
                target,
                "pg_restore",
                "-U",
                "rehearsal",
                "-d",
                name,
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                f"/rehearsal/{name}.dump",
            )
            require(
                schema(source, "source") == schema(target, name),
                "restored schema differs",
            )
            require(
                sql(target, name, "SELECT version_num FROM alembic_version") == head,
                "migration head mismatch",
            )
            print(
                f"PASS: {name} pg_dump/pg_restore, SHA256 transfer, schema and migration {head}"
            )

        snapshot("before_deletion")
        with Session(engine) as session:
            service = PrivacyService(session, PrivacySettings(_env_file=None))
            result = service.anonymize(ids[0])
            require(
                result.reports_deleted == 1 and not result.already_anonymized,
                "anonymization failed",
            )
            require(
                service.anonymize(ids[0]).already_anonymized,
                "repeat anonymization not idempotent",
            )
        snapshot("after_deletion")
        deleted, control = ids
        state_query = f"""SELECT json_build_object(
          'anonymized', a.anonymized_at IS NOT NULL,
          'payloads_erased', a.responses_json::jsonb = '{{"anonymized":true}}'::jsonb
             AND a.definition_json::jsonb = '{{"anonymized":true}}'::jsonb
             AND a.scores_json::jsonb = '{{"anonymized":true}}'::jsonb,
          'email_erased', i.email = 'deleted-' || replace(i.id::text, '-', '') || '@privacy.invalid',
          'revoked', i.status = 'revoked' AND i.revoked_at IS NOT NULL,
          'token_changed', i.token_hash <> '{hashlib.sha256(b"deleted").hexdigest()}',
          'reports', (SELECT count(*) FROM alignment_reports WHERE assessment_id = a.id),
          'audits', (SELECT count(*) FROM audit_events WHERE entity_id = a.id AND event_type = 'candidate_data.anonymized'))
          FROM assessments a JOIN assessment_invites i ON i.id = a.invite_id WHERE a.id = '{deleted}'"""
        post = json.loads(sql(target, "after_deletion", state_query))
        require(
            post
            == {
                "anonymized": True,
                "payloads_erased": True,
                "email_erased": True,
                "revoked": True,
                "token_changed": True,
                "reports": 0,
                "audits": 1,
            },
            "post-deletion state mismatch",
        )
        pre = json.loads(sql(target, "before_deletion", state_query))
        require(
            pre
            == {
                "anonymized": False,
                "payloads_erased": False,
                "email_erased": False,
                "revoked": False,
                "token_changed": False,
                "reports": 1,
                "audits": 0,
            },
            "pre-deletion counterexample missing",
        )
        for db in ("before_deletion", "after_deletion"):
            require(
                sql(
                    target,
                    db,
                    f"SELECT count(*) FROM assessments a JOIN assessment_invites i ON i.id=a.invite_id JOIN alignment_reports r ON r.assessment_id=a.id JOIN alignment_items ri ON ri.report_id=r.id WHERE a.id='{control}' AND a.anonymized_at IS NULL AND i.email='control@example.invalid' AND a.responses_json::jsonb='{{\"synthetic\":\"control\"}}'::jsonb",
                )
                == "1",
                "control changed",
            )
        require(
            sql(target, "after_deletion", "SELECT count(*) FROM alignment_items")
            == "1",
            "deleted report item survived",
        )
        # Exercise the restored append-only trigger, not just its schema text.
        try:
            sql(
                target,
                "after_deletion",
                "UPDATE audit_events SET event_type='synthetic-mutated'",
            )
        except subprocess.CalledProcessError as error:
            require(
                b"audit events are immutable" in error.stderr.lower(),
                "unexpected audit failure",
            )
        else:
            raise RuntimeError("restored audit protection missing")
        print(
            "PASS: post-deletion payloads, token, email, reports/items, audit tombstone and audit immutability"
        )
        print("PASS: unaffected synthetic control preserved in both restores")
        print(
            "EXPECTED UNSAFE: pre-deletion restore resurrects data and lacks deletion audit; external replay REQUIRED, NOT implemented or proven"
        )
    finally:
        if engine is not None:
            engine.dispose()
        os.environ.pop("DATABASE_URL", None)
        for cid in reversed(owned):
            label = (
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
            require(label == identity, "refusing cleanup of non-owned container")
            run(*docker, "rm", "--force", "--volumes", cid)
        print("Cleanup: removed only this run's owned containers and tmpfs snapshots")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        print(
            "FAIL: local subprocess failed; payload/connection output suppressed",
            file=sys.stderr,
        )
        sys.exit(1)
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
