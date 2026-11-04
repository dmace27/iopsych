"""Pure canonical snapshots of existing notice content, without policy defaults."""

import json
import re
from hashlib import sha256
from hmac import compare_digest
from typing import Any

_TEXT_FIELDS = frozenset(
    {
        "version",
        "purpose",
        "data_use",
        "retention",
        "accommodation_contact_email",
        "privacy_contact_email",
    }
)
_NOTICE_FIELDS = _TEXT_FIELDS | {"decline_without_penalty"}
_SNAPSHOT_FIELDS = {"schema_version", "consent_notice", "retention_days"}
_DIGEST = re.compile(r"[0-9a-f]{64}")


class InvalidNoticeSnapshotError(ValueError):
    """Stored content is absent, malformed, unsupported, or inconsistent."""


class NoticeReviewRequiredError(ValueError):
    """The client has not supplied the digest of the current frozen notice."""


def validate_notice_snapshot(payload: object) -> dict[str, Any]:
    """Validate exact JSON types and return an independent copy without normalization."""

    if type(payload) is not dict or payload.keys() != _SNAPSHOT_FIELDS:
        raise InvalidNoticeSnapshotError("Invalid snapshot fields")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise InvalidNoticeSnapshotError("Unsupported snapshot version")
    days = payload["retention_days"]
    if type(days) is not int or not 1 <= days <= 3650:
        raise InvalidNoticeSnapshotError("Invalid retention days")
    notice = payload["consent_notice"]
    if type(notice) is not dict or notice.keys() != _NOTICE_FIELDS:
        raise InvalidNoticeSnapshotError("Invalid notice fields")
    for field in _TEXT_FIELDS:
        value = notice[field]
        if type(value) is not str or not value.strip():
            raise InvalidNoticeSnapshotError("Invalid notice text")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise InvalidNoticeSnapshotError("Invalid notice Unicode") from exc
    if len(notice["version"]) > 80:
        raise InvalidNoticeSnapshotError("Notice version exceeds existing storage limit")
    if type(notice["decline_without_penalty"]) is not bool:
        raise InvalidNoticeSnapshotError("Invalid decline flag")
    return {"schema_version": 1, "consent_notice": dict(notice), "retention_days": days}


def build_notice_snapshot(notice: object, *, retention_days: int) -> dict[str, Any]:
    """Freeze already rendered content and its explicitly supplied existing setting."""

    return validate_notice_snapshot(
        {"schema_version": 1, "consent_notice": notice, "retention_days": retention_days}
    )


def canonical_notice_snapshot(payload: object) -> bytes:
    """Return sorted compact UTF-8 JSON, preserving every text code point."""

    return json.dumps(
        validate_notice_snapshot(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def notice_snapshot_hash(payload: object) -> str:
    """Hash the entire validated snapshot, including the frozen retention setting."""

    return sha256(canonical_notice_snapshot(payload)).hexdigest()


def require_presented_notice(
    payload: object, *, stored_sha256: object, presented_sha256: object
) -> dict[str, Any]:
    """Check integrity before presentation equality; the caller must hold its invite lock."""

    snapshot = validate_notice_snapshot(payload)
    actual = notice_snapshot_hash(snapshot)
    if (
        type(stored_sha256) is not str
        or _DIGEST.fullmatch(stored_sha256) is None
        or not compare_digest(actual, stored_sha256)
    ):
        raise InvalidNoticeSnapshotError("Stored notice digest mismatch")
    if (
        type(presented_sha256) is not str
        or _DIGEST.fullmatch(presented_sha256) is None
        or not compare_digest(actual, presented_sha256)
    ):
        raise NoticeReviewRequiredError("Review the current notice before recording a decision")
    return snapshot
