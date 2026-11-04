"""Bound actual HTTP body bytes and upload duration before application work."""

import anyio
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.runtime.config import RuntimeSettings
from app.security import security_headers


class RequestBodyLimitMiddleware:
    """Buffer a bounded body before routing so rejected streams cannot mutate data.

    Content-Length is deliberately not used as authority. One bytearray avoids
    per-chunk storage overhead, including streams of empty chunks. The ASGI
    server still owns framing, individual receive allocations and backpressure.
    """

    def __init__(self, app: ASGIApp, *, settings: RuntimeSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = bytearray()
        too_large = False
        try:
            with anyio.fail_after(self.settings.request_body_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > self.settings.max_request_body_bytes:
                        too_large = True
                        break
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await self._reject(scope, receive, send, status=408)
            return

        if too_large:
            await self._reject(scope, receive, send, status=413)
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                payload = bytes(body)
                body.clear()
                return {"type": "http.request", "body": payload, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, *, status: int) -> None:
        too_large = status == 413
        response = JSONResponse(
            {
                "type": "about:blank",
                "title": "Request body too large" if too_large else "Request body timeout",
                "status": status,
                "code": "request_body_too_large" if too_large else "request_body_timeout",
                "detail": (
                    "The request body exceeds the configured size limit."
                    if too_large
                    else "The request body was not received within the allowed time."
                ),
            },
            status_code=status,
            media_type="application/problem+json",
            headers=security_headers(scope["path"]),
        )
        await response(scope, receive, send)
