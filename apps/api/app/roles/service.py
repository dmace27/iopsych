"""Transactional role and immutable profile-version application service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext
from app.auth.errors import (
    organization_resource_not_found,
    resource_conflict,
    resource_validation_failed,
)
from app.database.models import (
    Role,
    RoleConstructRating,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
)
from app.database.repositories import OrganizationDataAccess
from app.database.session import commit_or_flush
from app.roles.schemas import (
    RoleCreateRequest,
    RoleProfileCreateRequest,
    RoleProfileResponse,
    RoleProfileUpdateRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from iopsych_contracts import CONSTRUCT_KEYS, ConstructKey
from iopsych_contracts import RoleConstructRating as RatingContract


class RoleProfileService:
    """Apply role/profile lifecycle rules inside one organization boundary."""

    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        """Bind database work to the authenticated actor and organization."""

        self._session = session
        self._context = context
        self._data = OrganizationDataAccess(
            session,
            context.organization.organization_id,
        )

    def list_roles(self) -> list[RoleResponse]:
        """Return every role in the tenant, including archived history."""

        return [RoleResponse.model_validate(role) for role in self._data.list_roles()]

    def get_role(self, role_id: UUID) -> Role:
        """Return a tenant-owned role or raise the non-disclosing 404."""

        role = self._data.get_role(role_id)
        if role is None:
            raise organization_resource_not_found()
        return role

    def create_role(self, request: RoleCreateRequest) -> Role:
        """Create a draft role owned by the authenticated organization."""

        role = Role(
            organization_id=self._context.organization.organization_id,
            title=request.title,
            department=request.department,
            location=request.location,
            job_description=request.job_description,
            status=RoleStatus.DRAFT,
        )
        self._session.add(role)
        commit_or_flush(self._session)
        return role

    def update_role(self, role_id: UUID, request: RoleUpdateRequest) -> Role:
        """Update editable metadata without invalidating historical evidence."""

        role = self._get_locked_role(role_id)
        self._require_role_editable(role)
        changes = request.model_dump(exclude_unset=True)
        if "job_description" in changes and self._data.list_role_profiles(role_id):
            raise resource_conflict(
                code="job_description_locked",
                detail="A job description cannot change after profile versioning begins.",
            )
        for field_name, value in changes.items():
            setattr(role, field_name, value)
        commit_or_flush(self._session)
        return role

    def archive_role(self, role_id: UUID) -> Role:
        """Soft-delete a role while retaining its immutable approval history."""

        role = self._get_locked_role(role_id)
        role.status = RoleStatus.ARCHIVED
        commit_or_flush(self._session)
        return role

    def create_profile(
        self,
        role_id: UUID,
        request: RoleProfileCreateRequest,
        *,
        assumptions: list[str] | None = None,
    ) -> RoleProfileResponse:
        """Create the next complete draft and supersede any open draft."""

        role = self._get_locked_role(role_id)
        self._require_role_editable(role)
        ratings = {rating.key: rating for rating in request.constructs}
        ordered_ratings = [ratings[key] for key in CONSTRUCT_KEYS]
        self._validate_evidence(role, ordered_ratings)
        next_version = self._next_profile_version(role_id)
        self._supersede_open_drafts(role_id)
        profile = self._insert_profile(
            role_id,
            next_version,
            ratings,
            assumptions=assumptions or [],
        )
        commit_or_flush(self._session)
        return self._profile_response(profile, ordered_ratings)

    def list_profiles(self, role_id: UUID) -> list[RoleProfileResponse]:
        """Return the complete version history for one tenant-owned role."""

        self.get_role(role_id)
        return [
            self._profile_response(profile, self._rating_contracts(profile.id))
            for profile in self._data.list_role_profiles(role_id)
        ]

    def get_profile(self, role_id: UUID, profile_id: UUID) -> RoleProfileResponse:
        """Return one version only when both route identifiers match the tenant."""

        profile = self._data.get_role_profile_for_role(role_id, profile_id)
        if profile is None:
            raise organization_resource_not_found()
        ratings = self._rating_contracts(profile.id)
        return self._profile_response(profile, ratings)

    def revise_profile(
        self,
        role_id: UUID,
        profile_id: UUID,
        request: RoleProfileUpdateRequest,
    ) -> RoleProfileResponse:
        """Copy a draft into a new version and apply the requested construct edits."""

        role = self._get_locked_role(role_id)
        self._require_role_editable(role)
        source = self._get_locked_profile(role_id, profile_id)
        if source.status is not RoleProfileStatus.DRAFT:
            raise resource_conflict(
                code="profile_not_editable",
                detail="Only the current draft profile can be revised.",
            )
        latest_version = self._latest_profile_version(role_id)
        if source.version != latest_version:
            raise resource_conflict(
                code="profile_not_latest",
                detail="Only the latest profile version can be revised.",
            )

        ratings = {rating.key: rating for rating in self._rating_contracts(source.id)}
        ratings.update({rating.key: rating for rating in request.constructs})
        ordered_ratings = [ratings[key] for key in CONSTRUCT_KEYS]
        self._validate_evidence(role, ordered_ratings)
        source.status = RoleProfileStatus.SUPERSEDED
        revised = self._insert_profile(
            role_id,
            source.version + 1,
            ratings,
            assumptions=source.assumptions_json,
        )
        commit_or_flush(self._session)
        return self._profile_response(revised, ordered_ratings)

    def approve_profile(self, role_id: UUID, profile_id: UUID) -> RoleProfileResponse:
        """Approve the latest draft and supersede the previously approved version."""

        role = self._get_locked_role(role_id)
        self._require_role_editable(role)
        profile = self._get_locked_profile(role_id, profile_id)
        if profile.status is not RoleProfileStatus.DRAFT:
            raise resource_conflict(
                code="profile_not_approvable",
                detail="Only a draft profile can be approved.",
            )
        if profile.version != self._latest_profile_version(role_id):
            raise resource_conflict(
                code="profile_not_latest",
                detail="Only the latest profile version can be approved.",
            )

        for prior in self._data.list_role_profiles(role_id):
            if prior.id != profile.id and prior.status is RoleProfileStatus.APPROVED:
                prior.status = RoleProfileStatus.SUPERSEDED
        profile.status = RoleProfileStatus.APPROVED
        profile.approved_by = self._context.user_id
        profile.approved_at = datetime.now(UTC)
        role.status = RoleStatus.ACTIVE
        ratings = self._rating_contracts(profile.id)
        commit_or_flush(self._session)
        return self._profile_response(profile, ratings)

    def _get_locked_role(self, role_id: UUID) -> Role:
        """Lock a tenant-owned role so version allocation is serialized."""

        statement = (
            select(Role)
            .where(
                Role.id == role_id,
                Role.organization_id == self._context.organization.organization_id,
            )
            .with_for_update()
        )
        role = self._session.scalar(statement)
        if role is None:
            raise organization_resource_not_found()
        return role

    def _get_locked_profile(self, role_id: UUID, profile_id: UUID) -> RoleProfile:
        """Lock a profile through its role and organization ownership chain."""

        statement = (
            select(RoleProfile)
            .join(Role, Role.id == RoleProfile.role_id)
            .where(
                RoleProfile.id == profile_id,
                RoleProfile.role_id == role_id,
                Role.organization_id == self._context.organization.organization_id,
            )
            .with_for_update()
        )
        profile = self._session.scalar(statement)
        if profile is None:
            raise organization_resource_not_found()
        return profile

    @staticmethod
    def _require_role_editable(role: Role) -> None:
        """Reject writes to archived roles while preserving read access."""

        if role.status is RoleStatus.ARCHIVED:
            raise resource_conflict(
                code="role_archived",
                detail="Archived roles cannot be changed.",
            )

    def _next_profile_version(self, role_id: UUID) -> int:
        """Allocate the next version while the owning role row is locked."""

        statement = select(func.max(RoleProfile.version)).where(RoleProfile.role_id == role_id)
        latest = self._session.scalar(statement)
        return (latest or 0) + 1

    def _latest_profile_version(self, role_id: UUID) -> int:
        """Return the current maximum version for a role with existing profiles."""

        # Callers have already loaded a profile for this role, so the allocated
        # next version is always at least two and this subtraction is safe.
        return self._next_profile_version(role_id) - 1

    def _supersede_open_drafts(self, role_id: UUID) -> None:
        """Ensure a role has at most one current draft after creation."""

        for profile in self._data.list_role_profiles(role_id):
            if profile.status is RoleProfileStatus.DRAFT:
                profile.status = RoleProfileStatus.SUPERSEDED

    def _insert_profile(
        self,
        role_id: UUID,
        version: int,
        ratings: dict[ConstructKey, RatingContract],
        *,
        assumptions: list[str],
    ) -> RoleProfile:
        """Insert one draft snapshot and all of its immutable construct rows."""

        profile = RoleProfile(
            role_id=role_id,
            version=version,
            status=RoleProfileStatus.DRAFT,
            created_by=self._context.user_id,
            assumptions_json=list(assumptions),
        )
        self._session.add(profile)
        self._session.flush()
        for key in CONSTRUCT_KEYS:
            rating = ratings[key]
            self._session.add(
                RoleConstructRating(
                    profile_id=profile.id,
                    construct_key=rating.key,
                    rating=rating.rating,
                    confidence=rating.confidence,
                    rationale=rating.rationale,
                    evidence_json=rating.evidence,
                )
            )
        self._session.flush()
        return profile

    def _rating_contracts(self, profile_id: UUID) -> list[RatingContract]:
        """Convert stored rows into stable shared-contract ordering."""

        stored = {
            rating.construct_key: rating
            for rating in self._data.list_role_construct_ratings(profile_id)
        }
        return [
            RatingContract(
                key=key,
                rating=stored[key].rating,
                confidence=stored[key].confidence,
                rationale=stored[key].rationale,
                evidence=stored[key].evidence_json,
            )
            for key in CONSTRUCT_KEYS
        ]

    @staticmethod
    def _validate_evidence(role: Role, ratings: list[RatingContract]) -> None:
        """Keep every profile evidence excerpt traceable to the role description."""

        for rating in ratings:
            if any(excerpt not in role.job_description for excerpt in rating.evidence):
                raise resource_validation_failed(
                    code="evidence_not_in_job_description",
                    detail=(
                        f"Evidence for {rating.key.value} must occur verbatim in the "
                        "job description."
                    ),
                )

    @staticmethod
    def _profile_response(
        profile: RoleProfile,
        ratings: list[RatingContract],
    ) -> RoleProfileResponse:
        """Build one complete profile response without lazy ORM relationships."""

        return RoleProfileResponse(
            id=profile.id,
            role_id=profile.role_id,
            version=profile.version,
            status=profile.status,
            created_by=profile.created_by,
            approved_by=profile.approved_by,
            approved_at=profile.approved_at,
            created_at=profile.created_at,
            assumptions=profile.assumptions_json,
            constructs=ratings,
        )
