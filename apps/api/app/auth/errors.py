"""Problem-detail exceptions shared by authorization and API domain layers."""

from dataclasses import dataclass, field
from typing import cast

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from iopsych_contracts import ApiFieldError, ApiProblem


@dataclass
class AccessProblemError(Exception):
    """A safe, machine-readable API failure rendered by one shared handler."""

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


def resource_conflict(*, code: str, detail: str) -> AccessProblemError:
    """Return a stable conflict for an invalid resource lifecycle transition."""

    return AccessProblemError(
        status=409,
        code=code,
        title="Resource conflict",
        detail=detail,
    )


def resource_validation_failed(*, code: str, detail: str) -> AccessProblemError:
    """Return a domain validation error that cannot be expressed structurally."""

    return AccessProblemError(
        status=422,
        code=code,
        title="Validation failed",
        detail=detail,
    )


def resource_unavailable(*, code: str, detail: str) -> AccessProblemError:
    """Return a non-disclosing gone response for an ended bearer lifecycle."""

    return AccessProblemError(
        status=410,
        code=code,
        title="Resource unavailable",
        detail=detail,
    )


def service_unavailable(*, code: str, detail: str) -> AccessProblemError:
    """Fail closed when a required security or delivery dependency is absent."""

    return AccessProblemError(
        status=503,
        code=code,
        title="Service unavailable",
        detail=detail,
    )


def upstream_delivery_failed() -> AccessProblemError:
    """Hide transactional-email provider details from API clients."""

    return AccessProblemError(
        status=502,
        code="invitation_delivery_failed",
        title="Invitation delivery failed",
        detail="The invitation could not be delivered. No active invitation was created.",
    )


def upstream_extraction_failed() -> AccessProblemError:
    """Hide provider output and error details when structured extraction fails."""

    return AccessProblemError(
        status=502,
        code="role_extraction_failed",
        title="Role extraction failed",
        detail="A valid role profile could not be extracted. No draft was created.",
    )


def rate_limit_exceeded(*, retry_after_seconds: int) -> AccessProblemError:
    """Return a standard throttling response with a bounded retry hint."""

    return AccessProblemError(
        status=429,
        code="rate_limit_exceeded",
        title="Too many requests",
        detail="Too many invitation requests were made. Try again later.",
        headers={"Retry-After": str(retry_after_seconds)},
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


async def request_validation_problem_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render FastAPI/Pydantic request errors using the shared API contract."""

    validation_error = cast(RequestValidationError, exc)
    field_errors = [
        ApiFieldError(
            pointer=_json_pointer(error["loc"]),
            code=str(error["type"]).replace(".", "_"),
            message=str(error["msg"]),
        )
        for error in validation_error.errors()
    ]
    problem = ApiProblem(
        title="Request validation failed",
        status=422,
        detail="One or more request values are invalid.",
        instance=request.url.path,
        code="request_validation_failed",
        errors=field_errors,
    )
    return JSONResponse(
        status_code=422,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def _json_pointer(location: tuple[str | int, ...]) -> str:
    """Convert a FastAPI error location into an escaped JSON Pointer."""

    parts = location[1:] if location and location[0] in {"body", "path", "query"} else location
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else ""
