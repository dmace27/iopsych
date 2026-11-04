"""Database schema probe, deliberately separate from process liveness."""

from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.database.config import API_ROOT

router = APIRouter(tags=["operations"])


def expected_schema_heads() -> set[str]:
    """Read expected revisions from the migration assets shipped with this API."""

    return set(ScriptDirectory(API_ROOT / "alembic").get_heads())


@router.get("/ready", responses={503: {"description": "Database unavailable"}})
def readiness(request: Request) -> JSONResponse:
    """Compare installed migration heads in a worker thread, without provider calls."""

    try:
        expected = expected_schema_heads()
    except Exception:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    if not expected:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    try:
        with request.app.state.session_factory() as session:
            actual = set(session.execute(text("SELECT version_num FROM alembic_version")).scalars())
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    if actual != expected:
        return JSONResponse({"status": "unavailable", "service": "api"}, status_code=503)
    return JSONResponse({"status": "ready", "service": "api"})
