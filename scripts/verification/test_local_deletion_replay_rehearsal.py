"""Fail-closed contract checks; no database or Docker access."""

import hashlib
from copy import deepcopy

import pytest
from local_deletion_replay_rehearsal import PROJECT, canonical, guard, validate_journal


@pytest.fixture
def payload():
    return {
        "version": 1,
        "run_id": "synthetic-run",
        "snapshot_sha256": "a" * 64,
        "entries": [
            {
                "tenant_id": "00000000-0000-4000-8000-000000000001",
                "assessment_id": "00000000-0000-4000-8000-000000000003",
                "deleted_at": "2026-11-04T23:00:00+00:00",
            }
        ],
    }


def validate(payload, **overrides):
    raw = canonical(payload)
    arguments = {
        "raw": raw,
        "digest": hashlib.sha256(raw).hexdigest(),
        "run_id": "synthetic-run",
        "snapshot_digest": "a" * 64,
    }
    return validate_journal(**(arguments | overrides))


def test_valid_minimal_journal(payload):
    assert validate(payload) == payload["entries"][0]


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "TEST_POSTGRES_URL",
        "PGHOST",
        "PGSERVICE",
        "PGPASSFILE",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
    ],
)
def test_reject_ambient_targets(tmp_path, key):
    with pytest.raises(RuntimeError, match="ambient"):
        guard(PROJECT, {key: ""}, tmp_path)


@pytest.mark.parametrize("project", [None, "other-project"])
def test_require_own_acknowledgement(tmp_path, project):
    with pytest.raises(RuntimeError, match="acknowledgement"):
        guard(project, {}, tmp_path)


@pytest.mark.parametrize("path", [".env", "apps/api/.env"])
def test_reject_dotenv(tmp_path, path):
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    with pytest.raises(RuntimeError, match=".env"):
        guard(PROJECT, {}, tmp_path)


def test_safe_environment(tmp_path):
    guard(PROJECT, {}, tmp_path)


@pytest.mark.parametrize(
    "key,value",
    [
        ("version", 2),
        ("version", True),
        ("run_id", "other-run"),
        ("snapshot_sha256", "b" * 64),
        ("entries", []),
        ("email", "synthetic@example.invalid"),
    ],
)
def test_reject_bad_envelope_even_with_recomputed_digest(payload, key, value):
    payload[key] = value
    with pytest.raises(RuntimeError):
        validate(payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("token", "synthetic"),
        ("email", "synthetic@example.invalid"),
        ("assessment_id", "not-a-uuid"),
        ("tenant_id", "not-a-uuid"),
        ("deleted_at", "2026-11-04T23:00:00"),
        ("deleted_at", "2026-11-04T23:00:00+01:00"),
    ],
)
def test_reject_invalid_or_sensitive_entry(payload, key, value):
    payload["entries"][0][key] = value
    with pytest.raises((RuntimeError, ValueError)):
        validate(payload)


def test_reject_tampering_against_separately_held_digest(payload):
    trusted = hashlib.sha256(canonical(payload)).hexdigest()
    changed = deepcopy(payload)
    changed["entries"][0]["assessment_id"] = "00000000-0000-4000-8000-000000000004"
    with pytest.raises(RuntimeError, match="integrity"):
        validate(changed, digest=trusted)


def test_reject_missing_field(payload):
    del payload["entries"][0]["tenant_id"]
    with pytest.raises(RuntimeError, match="fields"):
        validate(payload)
