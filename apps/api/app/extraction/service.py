"""Validated extraction orchestration and draft-only profile persistence."""

from __future__ import annotations

import time
from collections.abc import Callable
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
)
from app.roles.schemas import RoleProfileCreateRequest, RoleProfileResponse
from app.roles.service import RoleProfileService
from iopsych_contracts import parse_role_extraction


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
        for attempt in range(1, self._settings.max_attempts + 1):
            try:
                candidate = self._provider.extract(provider_input)
                extraction = parse_role_extraction(candidate, role.job_description)
                return self._profiles.create_profile(
                    role_id,
                    RoleProfileCreateRequest(constructs=extraction.constructs),
                    assumptions=extraction.assumptions,
                )
            except RoleExtractionConfigurationError as exc:
                raise service_unavailable(
                    code="role_extraction_unavailable",
                    detail="Role extraction is not configured.",
                ) from exc
            except RoleExtractionProviderError as exc:
                if not exc.retryable or attempt == self._settings.max_attempts:
                    raise upstream_extraction_failed() from exc
            except (ValidationError, ValueError) as exc:
                if attempt == self._settings.max_attempts:
                    raise upstream_extraction_failed() from exc

            delay = self._settings.retry_base_delay_seconds * (2 ** (attempt - 1))
            if delay:
                self._sleeper(delay)

        # Settings validation guarantees at least one attempt, and every final
        # failure branch raises above. This is a defensive invariant only.
        raise RuntimeError("bounded extraction loop exited without a result")  # pragma: no cover
