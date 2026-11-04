"""Start the development API with optional dotenv configuration, never shell code."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Load local overrides and retain the launcher's existing Uvicorn defaults."""

    # Local values historically override inherited variables. Disable expansion so
    # secrets and free text containing ${...}, backticks, or $() remain literal.
    load_dotenv(ROOT / "apps/api/.env", override=True, interpolate=False)
    os.chdir(ROOT)
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
            os.environ.get("API_HOST") or "0.0.0.0",
            "--port",
            os.environ.get("API_PORT") or "8000",
            "--log-level",
            os.environ.get("LOG_LEVEL") or "info",
        ],
    )


if __name__ == "__main__":
    main()
