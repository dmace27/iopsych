"""Smoke test the API workspace's shared-contract dependency."""

from iopsych_contracts import CONSTRUCT_KEYS, ComparisonTarget, ConstructKey
from iopsych_contracts.constructs import CONSTRUCT_DEFINITIONS_BY_KEY


def test_api_imports_shared_construct_definitions() -> None:
    """The FastAPI environment should consume the shared Pydantic package directly."""

    assert len(CONSTRUCT_KEYS) == 6
    assert (
        CONSTRUCT_DEFINITIONS_BY_KEY[ConstructKey.STRUCTURE].comparison_target
        is ComparisonTarget.INVERSE_ROLE_RATING
    )
