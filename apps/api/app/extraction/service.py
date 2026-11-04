"""Validated extraction orchestration and draft-only profile persistence."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Lock
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import resource_conflict, service_unavailable, upstream_extraction_failed
from app.database.models import RoleStatus
from app.extraction.config import RoleExtractionSettings
from app.extraction.provider import (
    RoleExtractionConfigurationError,
    RoleExtractionInput,
    RoleExtractionProvider,
    RoleExtractionProviderError,
    _extraction_deadline,
)
from app.roles.schemas import RoleProfileCreateRequest, RoleProfileResponse
from app.roles.service import RoleProfileService
from iopsych_contracts import RoleExtraction, parse_role_extraction

_admission_lock = Lock()
_active_roles: set[UUID] = set()


@contextmanager
def _admit_extraction(role_id: UUID, limit: int) -> Iterator[None]:
    """Fail fast without a queue; limits and duplicate suppression are process-local."""

    with _admission_lock:
        if role_id in _active_roles or len(_active_roles) >= limit:
            raise upstream_extraction_failed()
        _active_roles.add(role_id)
    try:
        yield
    finally:
        with _admission_lock:
            _active_roles.remove(role_id)


class StructuredRoleExtractionService:
    """Run an LLM extraction, validate it, and persist only a reviewable draft."""

    def __init__(
        self,
        session: Session,
        context: AuthorizationContext,
        provider: RoleExtractionProvider,
        settings: RoleExtractionSettings,
        *,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        """Bind extraction to an authenticated tenant and a narrow provider boundary."""

        self._profiles = RoleProfileService(session, context)
        self._provider = provider
        self._settings = settings
        self._sleeper = sleeper

    def extract(self, role_id: UUID) -> RoleProfileResponse:
        """Create a validated draft that still requires separate manager approval."""

        role = self._profiles.get_role(role_id)
        if role.status is RoleStatus.ARCHIVED:
            # Reject before any job-description content crosses the provider boundary.
            raise resource_conflict(
                code="role_archived",
                detail="Archived roles cannot be changed.",
            )

        provider_input = RoleExtractionInput(
            title=role.title,
            department=role.department,
            location=role.location,
            job_description=role.job_description,
        )
        with _admit_extraction(role_id, self._settings.max_concurrent_requests):
            deadline = time.monotonic() + self._settings.total_budget_seconds
            token = _extraction_deadline.set(deadline)
            try:
                extraction = self._extract_validated(provider_input, deadline)
                return self._profiles.create_profile(
                    role_id,
                    RoleProfileCreateRequest(constructs=extraction.constructs),
                    assumptions=extraction.assumptions,
                )
            finally:
                _extraction_deadline.reset(token)

    def _extract_validated(
        self, provider_input: RoleExtractionInput, deadline: float
    ) -> RoleExtraction:
        """Stop new work at the deadline and reject late results before persistence."""

        for attempt in range(1, self._settings.max_attempts + 1):
            if time.monotonic() >= deadline:
                raise upstream_extraction_failed()
            try:
                candidate = self._provider.extract(provider_input)
                extraction = parse_role_extraction(candidate, provider_input.job_description)
                if time.monotonic() >= deadline:
                    raise upstream_extraction_failed()
                return extraction
            except RoleExtractionConfigurationError:
                raise service_unavailable(
                    code="role_extraction_unavailable",
                    detail="Role extraction is not configured.",
                ) from None
            except RoleExtractionProviderError as exc:
                if not exc.retryable or attempt == self._settings.max_attempts:
                    raise upstream_extraction_failed() from None
            except (ValidationError, ValueError):
                if attempt == self._settings.max_attempts:
                    raise upstream_extraction_failed() from None

            delay = self._settings.retry_base_delay_seconds * (2 ** (attempt - 1))
            if delay >= deadline - time.monotonic():
                raise upstream_extraction_failed()
            if delay:
                self._sleeper(delay)

        # Settings validation guarantees at least one attempt, and every final
        # failure branch raises above. This is a defensive invariant only.
        raise RuntimeError("bounded extraction loop exited without a result")  # pragma: no cover
