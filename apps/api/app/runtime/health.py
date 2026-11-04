"""Database connectivity probe, deliberately separate from process liveness."""

from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(tags=["operations"])


@router.get("/ready", responses={503: {"description": "Database unavailable"}})
def readiness(request: Request) -> JSONResponse:
    """Probe connectivity in a worker thread, without paid provider calls.

    This does not certify schema compatibility or hosted configuration. Driver,
    pool and database deadlines must be configured separately: moving a query
    off the event loop does not bound its duration.
    """

    try:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    return JSONResponse({"status": "ready", "service": "api"})
