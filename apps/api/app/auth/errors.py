"""Problem-detail exceptions shared by auth and tenant authorization."""

from dataclasses import dataclass, field
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from iopsych_contracts import ApiProblem


@dataclass
class AccessProblemError(Exception):
    """A safe, machine-readable authentication or authorization failure."""

    status: int
    code: str
    title: str
    detail: str
    headers: dict[str, str] = field(default_factory=dict)


def authentication_required() -> AccessProblemError:
    """Return the intentionally generic response for invalid credentials."""

    return AccessProblemError(
        status=401,
        code="authentication_required",
        title="Authentication required",
        detail="Provide a valid bearer token for an active internal user.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authentication_unavailable() -> AccessProblemError:
    """Fail closed when the server has no configured token verifier."""

    return AccessProblemError(
        status=503,
        code="authentication_unavailable",
        title="Authentication unavailable",
        detail="Internal-user authentication is not configured.",
    )


def permission_denied() -> AccessProblemError:
    """Return a role denial without exposing the required policy."""

    return AccessProblemError(
        status=403,
        code="permission_denied",
        title="Permission denied",
        detail="Your internal-user role cannot perform this action.",
    )


def organization_resource_not_found() -> AccessProblemError:
    """Hide whether a requested resource belongs to another organization."""

    return AccessProblemError(
        status=404,
        code="resource_not_found",
        title="Resource not found",
        detail="The requested resource was not found.",
    )


async def access_problem_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render authorization failures using the shared RFC 9457 contract."""

    access_error = cast(AccessProblemError, exc)
    problem = ApiProblem(
        title=access_error.title,
        status=access_error.status,
        detail=access_error.detail,
        instance=request.url.path,
        code=access_error.code,
    )
    return JSONResponse(
        status_code=access_error.status,
        content=problem.model_dump(exclude_none=True),
        headers=access_error.headers,
        media_type="application/problem+json",
    )
