"""Distribution helper checks without dependency installs, service startup or provider calls."""

import importlib.util
import socket
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "distribution_manage", Path(__file__).resolve().parents[2] / "scripts/manage.py"
)
manage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manage)


def test_setup_preserves_configuration_and_database(tmp_path, monkeypatch):
    root = tmp_path / "checkout with spaces é"
    backend = root / "backend"
    backend.mkdir(parents=True)
    (root / "frontend").mkdir()
    (backend / ".env.example").write_text("MODEL_API_KEY=\n", encoding="utf-8")
    env = backend / ".env"
    env.write_text("OPERATOR=value\n", encoding="utf-8")
    database = backend / "existing.sqlite3"
    database.write_bytes(b"untouched database sentinel")
    calls = Mock()
    monkeypatch.setattr(manage, "ROOT", root)
    monkeypatch.setattr(manage, "BACKEND", backend)
    monkeypatch.setattr(manage, "run", calls)
    manage.setup("npm")
    manage.setup("npm")
    assert env.read_text() == "OPERATOR=value\n"
    assert database.read_bytes() == b"untouched database sentinel"
    env.unlink()
    manage.setup("npm")
    assert env.read_text() == "MODEL_API_KEY=\n"
    assert all(isinstance(call.args[0], list) for call in calls.call_args_list)


@pytest.mark.parametrize(
    "url",
    [
        "http://0.0.0.0:8000",
        "https://127.0.0.1:8000",
        "http://127.0.0.1:8000/path",
        "http://user@127.0.0.1:8000",
    ],
)
def test_start_rejects_nonlocal_or_ambiguous_addresses(url):
    with pytest.raises(ValueError):
        manage.address(url)


def test_start_detects_occupied_port_without_stopping_owner():
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        owner.listen()
        port = owner.getsockname()[1]
        with pytest.raises(ValueError, match="occupied"):
            manage.available(port)
        assert owner.fileno() >= 0
    assert manage.address("http://127.0.0.1:8123") == 8123


@pytest.mark.parametrize(
    "version, accepted",
    [
        ("v22.11.0", False),
        ("v22.12.0", True),
        ("v23.0.0", False),
        ("v24.14.0", True),
        ("v25.0.0", False),
        ("v26.0.0", True),
    ],
)
def test_prerequisites_follow_locked_test_runner_engine(monkeypatch, version, accepted):
    monkeypatch.setattr(manage, "executable", lambda name: name)
    monkeypatch.setattr(
        manage.subprocess,
        "check_output",
        lambda args, **kwargs: "11.9.0" if "npm" in args[0] else version,
    )
    if accepted:
        assert manage.prerequisites().startswith("npm")
    else:
        with pytest.raises(ValueError, match="Node.js"):
            manage.prerequisites()
