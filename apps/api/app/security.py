"""Response hardening and process-local abuse protection for the pilot API."""

from hashlib import sha256

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.auth.errors import access_problem_handler, rate_limit_exceeded
from app.invitations.rate_limit import InMemoryRateLimiter


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply headers and a peer budget before authentication or database work.

    Forwarded headers are deliberately ignored. A shared ingress limit is still
    required for multiple workers, and for browser proxies sharing one peer.
    """

    def __init__(self, app: ASGIApp, *, limit: int = 300) -> None:
        super().__init__(app)
        self.limiter = InMemoryRateLimiter()
        self.limit = limit

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Throttle all versioned routes, including invalid credentials and paths."""

        response: Response
        if request.url.path.startswith("/v1/"):
            peer = request.client.host if request.client else "unknown"
            key = sha256(peer.encode()).hexdigest()
            result = self.limiter.check(key, limit=self.limit, window_seconds=60)
            if not result.allowed:
                response = await access_problem_handler(
                    request, rate_limit_exceeded(retry_after_seconds=result.retry_after_seconds)
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers.update(security_headers(request.url.path))
        return response


def security_headers(path: str) -> dict[str, str]:
    """Protect all responses while preserving the existing interactive API docs.

    Swagger/Redoc serve only the public schema and load their own UI assets.
    Application JSON routes receive a deny-all CSP; docs retain frame denial.
    """

    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }
    if path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return headers


async def unexpected_problem_handler(request: Request, exc: Exception) -> JSONResponse:
    """Keep unhandled failures non-cacheable without reflecting exception details.

    Starlette handles unhandled failures outside user middleware. Set headers
    here too so even that outer error response obeys the privacy boundary.
    """

    return JSONResponse(
        status_code=500,
        content={
            "type": "about:blank",
            "title": "Internal service error",
            "status": 500,
            "code": "internal_service_error",
            "detail": "The request could not be completed. Try again later.",
        },
        headers=security_headers(request.url.path),
        media_type="application/problem+json",
    )
