"""Explicitly opted-in loopback login for the two existing synthetic seed users."""

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.config import AuthenticationSettings
from app.auth.dependencies import get_database_session
from app.auth.errors import authentication_required, organization_resource_not_found
from app.database.models import User
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_USER_ID,
)

router = APIRouter()
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
IDENTITIES = {
    "alpha": (
        ALPHA_USER_ID,
        ALPHA_ORGANIZATION_ID,
        "synthetic-alpha-recruiter",
        "recruiter@alpha.example.invalid",
    ),
    "beacon": (
        BEACON_USER_ID,
        BEACON_ORGANIZATION_ID,
        "synthetic-beacon-manager",
        "manager@beacon.example.invalid",
    ),
}


class LocalLoginRequest(BaseModel):
    """No arbitrary subjects, roles, email addresses, or tenant IDs are accepted."""

    model_config = ConfigDict(extra="forbid")
    identity: Literal["alpha", "beacon"]


def _segment(value: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


@router.post("/v1/auth/local-login")
def local_login(
    payload: LocalLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
) -> dict[str, str]:
    """Mint a short-lived token only after checking policy and exact seed identity."""

    settings: AuthenticationSettings = request.app.state.authentication_settings
    origin = urlsplit(settings.local_web_origin)
    if (
        not settings.local_login_enabled
        or settings.environment != "development"
        or origin.scheme != "http"
        or origin.hostname not in LOOPBACK
        or request.url.hostname not in LOOPBACK
        or request.client is None
        or request.client.host not in LOOPBACK
        or request.headers.get("origin", settings.local_web_origin) != settings.local_web_origin
        or settings.jwt_secret is None
    ):
        raise organization_resource_not_found()
    user_id, organization_id, subject, email = IDENTITIES[payload.identity]
    user = session.get(User, user_id)
    if user is None or (user.organization_id, user.auth_subject, user.email) != (
        organization_id,
        subject,
        email,
    ):
        raise authentication_required()
    now = int(time.time())
    content = f"{_segment({'alg': 'HS256', 'typ': 'JWT'})}.{
        _segment(
            {
                'sub': subject,
                'organization_id': str(organization_id),
                'iss': settings.jwt_issuer,
                'aud': settings.jwt_audience,
                'iat': now,
                'nbf': now,
                'exp': now + 900,
            }
        )
    }"
    signature = hmac.new(
        settings.jwt_secret.get_secret_value().encode(), content.encode(), hashlib.sha256
    ).digest()
    token = f"{content}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token}
