"""Pure validation boundaries for existing-account administration."""

import pytest
from pydantic import ValidationError

from app.accounts.schemas import AccountUpdateRequest


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"expected_version": 1},
        {"expected_version": 0, "is_active": False},
        {"expected_version": True, "is_active": False},
        {"expected_version": "1", "is_active": False},
        {"expected_version": 1, "role": None},
        {"expected_version": 1, "is_active": None},
        {"expected_version": 1, "is_active": "false"},
        {"expected_version": 1, "role": "owner"},
        {"expected_version": 1, "is_active": False, "organization_id": "other"},
        {"expected_version": 1, "role": "admin", "email": "new@example.invalid"},
    ],
)
def test_reject_invalid_updates(payload: dict[str, object]) -> None:
    """Only explicit supported account state can be mutated."""

    with pytest.raises(ValidationError):
        AccountUpdateRequest.model_validate(payload)


@pytest.mark.parametrize("role", ["admin", "recruiter", "hiring_manager"])
def test_accept_existing_roles(role: str) -> None:
    """Role updates preserve the established role vocabulary."""

    update = AccountUpdateRequest.model_validate({"expected_version": 2, "role": role})
    assert update.role == role


@pytest.mark.parametrize("active", [True, False])
def test_accept_activation(active: bool) -> None:
    """Both activation directions require an explicit boolean."""

    update = AccountUpdateRequest(expected_version=1, is_active=active)
    assert update.is_active is active


def test_canonical_fixtures_match_contract() -> None:
    """UI handoff examples remain parseable by the production contract."""

    from pathlib import Path

    from app.accounts.schemas import AccountListResponse

    fixtures = Path(__file__).parent / "fixtures" / "accounts"
    page = AccountListResponse.model_validate_json((fixtures / "page.json").read_text())
    update = AccountUpdateRequest.model_validate_json((fixtures / "update.json").read_text())
    assert page.items[0].version == update.expected_version
    assert page.next_cursor is None
