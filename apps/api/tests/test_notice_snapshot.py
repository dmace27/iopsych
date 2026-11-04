"""Synthetic, database-free notice snapshot contract checks."""

import copy
import hashlib
import json

import pytest

from app.privacy.notice_snapshot import (
    InvalidNoticeSnapshotError,
    NoticeReviewRequiredError,
    build_notice_snapshot,
    canonical_notice_snapshot,
    notice_snapshot_hash,
    require_presented_notice,
    validate_notice_snapshot,
)


def notice() -> dict[str, object]:
    return {
        "version": "synthetic-v1",
        "purpose": " Synthetic purpose — café. ",
        "data_use": "Synthetic use only.",
        "retention": "Synthetic retention: 90 days after submission.",
        "accommodation_contact_email": "access@example.invalid",
        "privacy_contact_email": "privacy@example.invalid",
        "decline_without_penalty": True,
    }


def test_canonical_bytes_hash_and_copy() -> None:
    source = notice()
    payload = build_notice_snapshot(source, retention_days=90)
    expected = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert canonical_notice_snapshot(payload) == expected
    assert notice_snapshot_hash(payload) == hashlib.sha256(expected).hexdigest()
    assert notice_snapshot_hash(dict(reversed(list(payload.items())))) == notice_snapshot_hash(
        payload
    )
    source["purpose"] = "Changed"
    assert payload["consent_notice"]["purpose"] == " Synthetic purpose — café. "
    validated = validate_notice_snapshot(payload)
    validated["consent_notice"]["purpose"] = "Changed again"
    assert validated != payload


@pytest.mark.parametrize("days", [True, False, "90", 90.0, 0, 3651, None])
def test_reject_invalid_days(days: object) -> None:
    with pytest.raises(InvalidNoticeSnapshotError):
        validate_notice_snapshot(
            {"schema_version": 1, "consent_notice": notice(), "retention_days": days}
        )


@pytest.mark.parametrize("version", [True, 1.0, "1", 2, None])
def test_reject_unknown_or_coerced_version(version: object) -> None:
    payload = build_notice_snapshot(notice(), retention_days=90)
    payload["schema_version"] = version
    with pytest.raises(InvalidNoticeSnapshotError):
        validate_notice_snapshot(payload)


@pytest.mark.parametrize("payload", [None, [], {}, {"unexpected": 1}])
def test_unknown_legacy_payload_is_not_reconstructed(payload: object) -> None:
    with pytest.raises(InvalidNoticeSnapshotError):
        validate_notice_snapshot(payload)


@pytest.mark.parametrize("value", [None, [], {}, {**notice(), "extra": "forbidden"}])
def test_reject_incomplete_notice(value: object) -> None:
    with pytest.raises(InvalidNoticeSnapshotError):
        build_notice_snapshot(value, retention_days=90)


@pytest.mark.parametrize("value", [None, 42, "", "  ", "\ud800"])
def test_reject_invalid_text(value: object) -> None:
    source = notice()
    source["purpose"] = value
    with pytest.raises(InvalidNoticeSnapshotError):
        build_notice_snapshot(source, retention_days=90)


def test_reject_overlong_version_and_coerced_boolean() -> None:
    source = notice()
    source["version"] = "v" * 81
    with pytest.raises(InvalidNoticeSnapshotError):
        build_notice_snapshot(source, retention_days=90)
    source = notice()
    source["decline_without_penalty"] = 1
    with pytest.raises(InvalidNoticeSnapshotError):
        build_notice_snapshot(source, retention_days=90)


@pytest.mark.parametrize("field", list(notice()))
def test_every_displayed_field_changes_digest(field: str) -> None:
    original = build_notice_snapshot(notice(), retention_days=90)
    changed = copy.deepcopy(original)
    changed["consent_notice"][field] = (
        False if field == "decline_without_penalty" else original["consent_notice"][field] + "!"
    )
    assert notice_snapshot_hash(original) != notice_snapshot_hash(changed)


def test_retention_setting_changes_digest_and_boundary_values_are_valid() -> None:
    snapshots = [build_notice_snapshot(notice(), retention_days=days) for days in (1, 90, 3650)]
    assert len({notice_snapshot_hash(payload) for payload in snapshots}) == 3


@pytest.mark.parametrize("presented", [None, "", "a" * 64, "A" * 64, 90])
def test_missing_malformed_or_stale_presentation_requires_review(presented: object) -> None:
    payload = build_notice_snapshot(notice(), retention_days=90)
    with pytest.raises(NoticeReviewRequiredError):
        require_presented_notice(
            payload, stored_sha256=notice_snapshot_hash(payload), presented_sha256=presented
        )


@pytest.mark.parametrize("stored", [None, "", "a" * 64, "A" * 64, 90])
def test_stored_integrity_failure_is_distinct_from_stale_presentation(stored: object) -> None:
    payload = build_notice_snapshot(notice(), retention_days=90)
    with pytest.raises(InvalidNoticeSnapshotError):
        require_presented_notice(payload, stored_sha256=stored, presented_sha256=None)


def test_matching_digest_and_configuration_change() -> None:
    original = build_notice_snapshot(notice(), retention_days=90)
    digest = notice_snapshot_hash(original)
    assert (
        require_presented_notice(original, stored_sha256=digest, presented_sha256=digest)
        == original
    )
    changed = build_notice_snapshot(notice(), retention_days=91)
    with pytest.raises(NoticeReviewRequiredError):
        require_presented_notice(
            changed, stored_sha256=notice_snapshot_hash(changed), presented_sha256=digest
        )
    with pytest.raises(InvalidNoticeSnapshotError):
        require_presented_notice(changed, stored_sha256=digest, presented_sha256=digest)
