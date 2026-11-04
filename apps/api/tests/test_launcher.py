"""Exercise the committed Bash/Python launcher with real uvicorn, not source text."""

import os
import runpy
import shutil
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.auth.config import AuthenticationSettings

ROOT = Path(__file__).resolve().parents[3]


def test_actual_launcher_dotenv_and_exported_overrides(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "apps/api/app").mkdir(parents=True)
    (tmp_path / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    for name in ("run-api.sh", "run-api.py"):
        shutil.copy(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    marker = tmp_path / "executed-shell"
    template = (ROOT / "apps/api/.env.example").read_text()
    (tmp_path / "apps/api/.env").write_text(
        template
        + f"\nAPI_PORT=1\nAPI_HOST=invalid.example\nPROBE=$(touch {marker})\nLITERAL=${{HOME}}\n"
    )
    (tmp_path / "apps/api/app/__init__.py").touch()
    (tmp_path / "apps/api/app/main.py").write_text("""import os
from fastapi import FastAPI
app = FastAPI()
@app.get("/health")
def health():
    return {key: os.environ[key] for key in ["INVITE_RETENTION_STATEMENT", "PROBE", "LITERAL"]}
""")
    env = {**os.environ, "API_HOST": "127.0.0.1", "API_PORT": "8113", "LOG_LEVEL": "warning"}
    env.pop("INVITE_RETENTION_STATEMENT", None)
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(
            ["bash", str(tmp_path / "scripts/run-api.sh")],
            cwd="/tmp",
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            for _ in range(100):
                assert process.poll() is None, "launcher exited before becoming healthy"
                try:
                    response = httpx.get("http://127.0.0.1:8113/health", timeout=0.2)
                    if response.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("launcher did not become healthy")
            assert response.json() == {
                "INVITE_RETENTION_STATEMENT": (
                    "Pilot data is retained for {retention_days} days "
                    "after submission, then anonymized."
                ),
                "PROBE": f"$(touch {marker})",
                "LITERAL": "${HOME}",
            }
            assert not marker.exists()
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)


def test_local_login_refuses_wildcard_listener() -> None:
    result = subprocess.run(
        ["bash", "scripts/run-api.sh"],
        cwd=ROOT,
        env={**os.environ, "AUTH_LOCAL_LOGIN_ENABLED": "true", "API_HOST": "0.0.0.0"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "requires a loopback" in result.stderr


TRUE_VALUES = ["1", "true", "TRUE", "True", "t", "T", "yes", "YES", "y", "Y", "on", "ON"]
FALSE_VALUES = ["0", "false", "FALSE", "False", "f", "F", "no", "NO", "n", "N", "off", "OFF"]


@pytest.mark.parametrize("value", TRUE_VALUES)
@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1", "remote.example.invalid"])
def test_enabled_spellings_refuse_nonloopback(value: str, host: str) -> None:
    with (
        patch.dict(os.environ, {"AUTH_LOCAL_LOGIN_ENABLED": value, "API_HOST": host}, clear=True),
        patch("dotenv.load_dotenv"),
        patch("os.execv") as execute,
    ):
        assert AuthenticationSettings(_env_file=None).local_login_enabled is True
        with pytest.raises(SystemExit, match="requires a loopback"):
            runpy.run_path(str(ROOT / "scripts/run-api.py"))
        execute.assert_not_called()


@pytest.mark.parametrize("value", [*FALSE_VALUES, None])
def test_disabled_spellings_allow_listener(value: str | None) -> None:
    env = {"API_HOST": "0.0.0.0"}
    if value is not None:
        env["AUTH_LOCAL_LOGIN_ENABLED"] = value
    with (
        patch.dict(os.environ, env, clear=True),
        patch("dotenv.load_dotenv"),
        patch("os.execv") as execute,
    ):
        assert AuthenticationSettings(_env_file=None).local_login_enabled is False
        runpy.run_path(str(ROOT / "scripts/run-api.py"))
        execute.assert_called_once()


@pytest.mark.parametrize("value", ["", "enabled", "2", " true ", "false-ish"])
def test_invalid_boolean_fails_closed(value: str) -> None:
    with (
        patch.dict(
            os.environ, {"AUTH_LOCAL_LOGIN_ENABLED": value, "API_HOST": "127.0.0.1"}, clear=True
        ),
        patch("dotenv.load_dotenv"),
        patch("os.execv") as execute,
    ):
        with pytest.raises(SystemExit, match="must be a valid boolean"):
            runpy.run_path(str(ROOT / "scripts/run-api.py"))
        execute.assert_not_called()


@pytest.mark.parametrize("value", TRUE_VALUES)
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_enabled_spellings_allow_loopback(value: str, host: str) -> None:
    with (
        patch.dict(os.environ, {"AUTH_LOCAL_LOGIN_ENABLED": value, "API_HOST": host}, clear=True),
        patch("dotenv.load_dotenv"),
        patch("os.execv") as execute,
    ):
        runpy.run_path(str(ROOT / "scripts/run-api.py"))
        execute.assert_called_once()
        arguments = execute.call_args.args[1]
        assert arguments[arguments.index("--host") + 1] == host
