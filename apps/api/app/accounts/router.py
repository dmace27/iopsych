"""Administrator-only routes for existing internal accounts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.accounts.schemas import AccountListResponse, AccountResponse, AccountUpdateRequest
from app.accounts.service import discover_accounts, update_account
from app.audit import audited
from app.auth.context import AuthorizationContext
from app.auth.dependencies import get_database_session, require_roles
from app.database.models import InternalUserRole

router = APIRouter(prefix="/v1/accounts", tags=["internal accounts"])
AdminContext = Annotated[AuthorizationContext, Depends(require_roles(InternalUserRole.ADMIN))]
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/users", response_model=AccountListResponse)
@audited("account.users_discovered", "user")
def list_accounts(
    response: Response,
    context: AdminContext,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    after: UUID | None = None,
) -> AccountListResponse:
    """Discover accounts within the current organization."""

    response.headers["Cache-Control"] = "no-store"
    return discover_accounts(session, context, limit=limit, after=after)


@router.patch("/users/{user_id}", response_model=AccountResponse)
@audited("account.access_change_requested", "user", entity_id_path_parameter="user_id")
def change_account(
    user_id: UUID,
    update: AccountUpdateRequest,
    response: Response,
    context: AdminContext,
    session: DatabaseSession,
) -> AccountResponse:
    """Change only existing account role and activation state."""

    response.headers["Cache-Control"] = "no-store"
    return update_account(session, context, user_id, update)
