"""Hermetic harness safety checks: no application imports or Docker mutations."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "rehearsal", Path(__file__).with_name("local_delivery_rehearsal.py")
)
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)


@pytest.mark.parametrize("project", [None, "", "iopsych", "iopsych-restore-rehearsal"])
def test_opt_in(project, tmp_path):
    with pytest.raises(RuntimeError, match="opt-in"):
        rehearsal.guard(project, {}, tmp_path)


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "DATABASE_ECHO",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "PGHOST",
        "PGSERVICEFILE",
        "TEST_DELIVERY_POSTGRES_URL",
        "AUTH_JWT_SECRET",
        "INVITE_LOCAL_QUEUE_KEY",
        "OPENAI_API_KEY",
        "ROLE_EXTRACTION_API_KEY",
    ],
)
def test_ambient_targets_rejected_even_empty(key, tmp_path):
    with pytest.raises(RuntimeError, match="ambient"):
        rehearsal.guard(rehearsal.PROJECT, {key: ""}, tmp_path)


@pytest.mark.parametrize("name", [".env", "apps/api/.env"])
def test_dotenv_rejected(name, tmp_path):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    with pytest.raises(RuntimeError, match=".env"):
        rehearsal.guard(rehearsal.PROJECT, {}, tmp_path)


def test_safe_environment(tmp_path):
    rehearsal.guard(rehearsal.PROJECT, {"PATH": "/usr/bin"}, tmp_path)


@pytest.mark.parametrize(
    "endpoint",
    [
        "tcp://127.0.0.1:2375",
        "ssh://host",
        "unix://remote/socket",
        "unix:///tmp/socket?remote=x",
        "unix:///tmp/socket\n",
    ],
)
def test_remote_or_ambiguous_docker_rejected(endpoint):
    with pytest.raises(RuntimeError, match="Unix"):
        rehearsal.local_endpoint(endpoint)


def test_unix_docker_accepted():
    assert (
        rehearsal.local_endpoint("unix:///tmp/docker.sock") == "unix:///tmp/docker.sock"
    )


@pytest.mark.parametrize("kind", ["container", "network"])
def test_cleanup_refuses_foreign_owner(kind):
    with (
        patch.object(rehearsal, "run", return_value="foreign") as run,
        pytest.raises(RuntimeError, match="non-owned"),
    ):
        rehearsal.owned_cleanup(
            ["docker", "--host", "unix:///tmp/docker.sock"], kind, "id", "mine"
        )
    assert run.call_count == 1


@pytest.mark.parametrize("kind", ["container", "network"])
def test_cleanup_removes_only_inspected_resource(kind):
    with patch.object(rehearsal, "run", return_value="mine") as run:
        rehearsal.owned_cleanup(["docker"], kind, "unique-owned-id", "mine")
    assert run.call_count == 2
    assert run.call_args.args[-1] == "unique-owned-id"
    assert "prune" not in run.call_args.args


def test_no_opt_in_never_calls_docker(tmp_path):
    with (
        patch("sys.argv", ["rehearsal"]),
        patch.dict("os.environ", {}, clear=True),
        patch.object(rehearsal, "run") as run,
        pytest.raises(RuntimeError, match="opt-in"),
    ):
        rehearsal.main()
    run.assert_not_called()


def test_reserved_ports_are_disjoint():
    assert rehearsal.PORTS == (5599, 1140, 8140)
    assert not set(rehearsal.PORTS) & {3000, 8000, 8001, 5432}
