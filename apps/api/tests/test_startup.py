"""Exercise the actual development launcher with isolated local configuration."""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]


def available_port() -> int:
    """Ask the OS for a loopback port for this short-lived test server."""

    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


@pytest.mark.parametrize("configuration", ["example", "unquoted-text", "no-file"])
def test_launcher_reaches_health_with_local_configuration(
    tmp_path: Path, configuration: str
) -> None:
    """Boot real FastAPI without a database or provider, then clean up reload children.

    A temporary repository layout keeps developer .env files untouched. Copying
    the real application also ensures its settings resolve against this layout.
    """

    checkout = tmp_path / "checkout"
    scripts = checkout / "scripts"
    scripts.mkdir(parents=True)
    for name in ("run-api.sh", "run_api.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    api = checkout / "apps/api"
    shutil.copytree(
        ROOT / "apps/api/app", api / "app", ignore=shutil.ignore_patterns("__pycache__")
    )
    # The launcher must use the installed environment, just as a fresh setup does.
    (checkout / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)

    example = ROOT / "apps/api/.env.example"
    environment = dict(os.environ)
    for name in dotenv_values(example, interpolate=False):
        environment.pop(name, None)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHON_DOTENV_DISABLED", None)
    port = available_port()
    environment.update(API_HOST="127.0.0.1", API_PORT=str(port), LOG_LEVEL="warning")

    marker = tmp_path / "configuration-was-executed"
    if configuration != "no-file":
        content = example.read_text(encoding="utf-8")
        content = content.replace("API_HOST=0.0.0.0", "API_HOST=127.0.0.1")
        content = content.replace("API_PORT=8000", f"API_PORT={port}")
        if configuration == "unquoted-text":
            content = content.replace(
                'INVITE_RETENTION_STATEMENT="Pilot data is retained for '
                '{retention_days} days after submission, then anonymized."',
                "INVITE_RETENTION_STATEMENT=Pilot data is retained for "
                "{retention_days} days after submission, then anonymized.",
            )
        # A shell-sourced file would execute both command-substitution forms.
        content += f"\nSTARTUP_LITERAL=$(touch '{marker}') `touch '{marker}'` ${{PATH}}\n"
        (api / ".env").write_text(content, encoding="utf-8")
        # An invalid inherited port proves that the file still takes precedence.
        environment["API_PORT"] = "invalid-inherited-port"

    with (tmp_path / "startup.log").open("wb") as log:
        process = subprocess.Popen(
            ["bash", str(scripts / "run-api.sh")],
            cwd=tmp_path,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                assert process.poll() is None, "API launcher exited before health was reachable"
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        assert response.status == 200
                        assert json.load(response) == {
                            "status": "ok",
                            "service": "api",
                            "version": "0.1.0",
                        }
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                pytest.fail("API launcher did not become healthy within 30 seconds")
            assert not marker.exists(), "Configuration was executed as shell code"
        finally:
            # Uvicorn reload spawns a child; terminate the entire process group.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
