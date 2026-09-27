"""Append-only audit middleware for authenticated sensitive API actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar, cast
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.auth.context import AuthorizationContext
from app.database.models import AuditEvent
from iopsych_contracts import ApiProblem

P = ParamSpec("P")
R = TypeVar("R")
AUDIT_POLICY_ATTRIBUTE = "__iopsych_audit_policy__"
AUDIT_ENTITY_STATE_ATTRIBUTE = "audit_entity_id"


@dataclass(frozen=True)
class AuditPolicy:
    """Describe one endpoint action and how to identify its target entity."""

    event_type: str
    entity_type: str
    entity_id_path_parameter: str | None = None


def audited(
    event_type: str,
    entity_type: str,
    *,
    entity_id_path_parameter: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Mark an endpoint so middleware records every authenticated outcome."""

    if not event_type.strip() or not entity_type.strip():
        raise ValueError("audit event and entity types cannot be blank")
    policy = AuditPolicy(
        event_type=event_type,
        entity_type=entity_type,
        entity_id_path_parameter=entity_id_path_parameter,
    )

    def decorate(endpoint: Callable[P, R]) -> Callable[P, R]:
        """Attach policy metadata without changing sync or async execution."""

        setattr(endpoint, AUDIT_POLICY_ATTRIBUTE, policy)
        return endpoint

    return decorate


class AuditMiddleware(BaseHTTPMiddleware):
    """Persist audit events before returning sensitive endpoint responses."""

    def __init__(self, app: Any, *, session_factory: sessionmaker[Session]) -> None:
        """Bind the append-only writer to the application's database."""

        super().__init__(app)
        self._session_factory = session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Run the endpoint and append every authenticated outcome, including exceptions."""

        try:
            response = await call_next(request)
        except Exception:
            # Starlette's outer error middleware will render the final 500. The
            # audit entry must be committed before the exception leaves this
            # middleware or the failed sensitive action would disappear.
            audit_failure = self._append_event(request, status_code=500)
            if audit_failure is not None:
                return audit_failure
            raise

        audit_failure = self._append_event(request, status_code=response.status_code)
        return audit_failure or response

    def _append_event(self, request: Request, *, status_code: int) -> JSONResponse | None:
        """Persist one event when the resolved endpoint and actor are auditable."""

        endpoint = request.scope.get("endpoint")
        policy = getattr(endpoint, AUDIT_POLICY_ATTRIBUTE, None)
        context = getattr(request.state, "authorization_context", None)
        if not isinstance(policy, AuditPolicy) or not isinstance(context, AuthorizationContext):
            return None

        explicit_entity_id = getattr(request.state, AUDIT_ENTITY_STATE_ATTRIBUTE, None)
        if isinstance(explicit_entity_id, UUID):
            entity_id, target_is_valid = explicit_entity_id, True
        else:
            entity_id, target_is_valid = self._resolve_entity_id(request, policy, context)
        metadata = {
            "http_method": request.method,
            "http_status": status_code,
            "outcome": _outcome_for_status(status_code),
        }
        if not target_is_valid:
            metadata["target_path_parameter_valid"] = False
        event = AuditEvent(
            organization_id=context.organization.organization_id,
            actor_id=context.user_id,
            event_type=policy.event_type,
            entity_type=policy.entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
        try:
            with self._session_factory() as session:
                session.add(event)
                session.commit()
        except SQLAlchemyError:
            # Sensitive operations fail closed when their required audit trail
            # cannot be written. No database exception detail reaches clients.
            return _audit_failure_response(request)
        return None

    @staticmethod
    def _resolve_entity_id(
        request: Request,
        policy: AuditPolicy,
        context: AuthorizationContext,
    ) -> tuple[UUID, bool]:
        """Resolve a UUID route target, falling back safely to the actor ID."""

        parameter = policy.entity_id_path_parameter
        if parameter is None:
            return context.user_id, True
        raw_value = request.path_params.get(parameter)
        try:
            return UUID(str(raw_value)), True
        except ValueError:
            # A rejected malformed route still needs an attributable event.
            return context.user_id, False


def _outcome_for_status(status_code: int) -> str:
    """Map HTTP status classes to compact audit outcomes."""

    if status_code < 400:
        return "succeeded"
    if status_code < 500:
        return "rejected"
    return "failed"


def _audit_failure_response(request: Request) -> JSONResponse:
    """Return a stable problem response when a mandatory audit append fails."""

    problem = ApiProblem(
        title="Audit persistence failed",
        status=500,
        detail="The sensitive action could not be recorded safely.",
        instance=request.url.path,
        code="audit_persistence_failed",
    )
    return JSONResponse(
        status_code=500,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def get_audit_policy(endpoint: object) -> AuditPolicy | None:
    """Expose attached policy metadata for tests and integration tooling."""

    return cast(AuditPolicy | None, getattr(endpoint, AUDIT_POLICY_ATTRIBUTE, None))


def set_audit_entity(request: Request, entity_id: UUID) -> None:
    """Attribute a create/version action to the entity produced by its endpoint."""

    setattr(request.state, AUDIT_ENTITY_STATE_ATTRIBUTE, entity_id)
