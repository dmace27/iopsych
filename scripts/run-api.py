"""Load dotenv as data, preserving exported overrides, then exec the real server."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "apps/api/.env", override=False, interpolate=False)
os.chdir(ROOT)
# Local login must never be exposed by accidentally widening the listener.
try:
    local_login_enabled = TypeAdapter(bool).validate_python(
        os.environ.get("AUTH_LOCAL_LOGIN_ENABLED", "false")
    )
except ValidationError:
    raise SystemExit("AUTH_LOCAL_LOGIN_ENABLED must be a valid boolean") from None
if local_login_enabled and os.environ.get("API_HOST", "127.0.0.1") not in {
    "127.0.0.1",
    "::1",
    "localhost",
}:
    raise SystemExit("Local synthetic login requires a loopback API_HOST")
os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--no-proxy-headers",
        "--app-dir",
        "apps/api",
        "--host",
        os.environ.get("API_HOST", "127.0.0.1"),
        "--port",
        os.environ.get("API_PORT", "8101"),
        "--log-level",
        os.environ.get("LOG_LEVEL", "info"),
    ],
)
