import io
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.inspection_models import InspectionError
from app.services import git_capture
from app.services.git_capture import (
    AuthorizedRepository,
    authorize_repositories,
    capture_changes,
)
from tests.test_parser import SIMPLE


@pytest.fixture
def authorized(tmp_path):
    (tmp_path / ".git").mkdir()
    return AuthorizedRepository("project", tmp_path.resolve())


@pytest.fixture
def git_mock(monkeypatch):
    calls = []

    def install(diff=None, *, config_code=1, config=b"", state=b"true\nfalse\n", diff_code=0):
        def run(root, arguments, limit):
            calls.append((root, arguments, limit))
            if arguments[0] == "config":
                return config_code, config
            if arguments[0] == "rev-parse":
                return 0, state
            assert arguments[0] == "diff"
            return diff_code, SIMPLE.encode() if diff is None else diff

        monkeypatch.setattr(git_capture, "_run_git", run)

    install()
    return install, calls


def test_authorization_requires_explicit_absolute_roots(tmp_path):
    mapping = authorize_repositories([f"project={tmp_path}"])
    assert mapping["project"].root == tmp_path.resolve()
    for entries in [
        [],
        ["project=relative"],
        [f"../bad={tmp_path}"],
        [f"project={tmp_path}", f"project={tmp_path}"],
        [f"missing={tmp_path / 'absent'}"],
    ]:
        with pytest.raises(ValueError):
            authorize_repositories(entries)


@pytest.mark.parametrize("scope", ["staged", "unstaged"])
def test_capture_selects_one_scope_and_fixed_safe_options(authorized, git_mock, scope):
    _, calls = git_mock
    assert capture_changes(authorized, scope) == SIMPLE
    assert len(calls) == 3
    root, arguments, limit = calls[-1]
    assert root == authorized.root
    assert ("--cached" in arguments) == (scope == "staged")
    assert arguments[-1] == "--"
    assert "--no-ext-diff" in arguments and "--no-textconv" in arguments
    assert "--ignore-submodules=all" in arguments
    assert "--no-renames" in arguments
    assert "--src-prefix=a/" in arguments and "--dst-prefix=b/" in arguments
    assert limit == 1024 * 1024
    assert all("ls-files" not in args for _, args, _ in calls)


def test_no_changes_does_not_invent_untracked_content(authorized, git_mock):
    install, _ = git_mock
    (authorized.root / "untracked.txt").write_text("not included")
    install(diff=b"")
    assert capture_changes(authorized, "unstaged") == ""


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ({"config_code": 0, "config": b"filter.test.clean do-not-run"}, "unsafe_git_config"),
        ({"config_code": 0, "config": b"include.path outside"}, "unsafe_git_config"),
        ({"config_code": 128}, "git_error"),
        ({"state": b"false\ntrue\n"}, "invalid_repository"),
        ({"diff_code": 128, "diff": b"private-stderr-token"}, "git_error"),
        ({"diff": b"\xff"}, "unsupported_encoding"),
    ],
)
def test_git_errors_are_recoverable_and_sanitized(authorized, git_mock, options, code):
    install, _ = git_mock
    install(**options)
    with pytest.raises(InspectionError) as exc:
        capture_changes(authorized, "unstaged")
    assert exc.value.code == code
    assert "private-stderr-token" not in str(exc.value)


def test_filters_and_includes_block_before_any_diff(authorized, git_mock):
    install, calls = git_mock
    install(config_code=0, config=b"includeif.gitdir.path dangerous")
    with pytest.raises(InspectionError, match="filtros/includes"):
        capture_changes(authorized, "unstaged")
    assert len(calls) == 1
    assert "--no-includes" in calls[0][1]


def test_invalid_repository_and_scope_before_git(tmp_path, git_mock):
    _, calls = git_mock
    with pytest.raises(InspectionError) as exc:
        capture_changes(AuthorizedRepository("project", tmp_path), "unstaged")
    assert exc.value.code == "invalid_repository"
    with pytest.raises(InspectionError) as exc:
        capture_changes(AuthorizedRepository("project", tmp_path), "all")
    assert exc.value.code == "invalid_scope"
    assert not calls


@pytest.mark.parametrize(
    "name", ["commondir", "objects/info/alternates", "objects/info/http-alternates"]
)
def test_external_git_storage_is_rejected(authorized, git_mock, name):
    path = authorized.root / ".git" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("external")
    with pytest.raises(InspectionError) as exc:
        capture_changes(authorized, "unstaged")
    assert exc.value.code == "unsafe_git_layout"
    assert not git_mock[1]


def test_redirected_metadata_is_rejected(authorized, git_mock, monkeypatch):
    link = authorized.root / ".git" / "objects"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(InspectionError) as exc:
        capture_changes(authorized, "unstaged")
    assert exc.value.code == "unsafe_git_layout"
    assert not git_mock[1]


class FakeProcess:
    def __init__(self, data=b"", code=0):
        self.stdout = io.BytesIO(data)
        self.code = code
        self.killed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stdout.close()

    def kill(self):
        self.killed = True

    def wait(self):
        return self.code


def test_runner_bounds_output_and_never_uses_a_shell(monkeypatch, tmp_path):
    process = FakeProcess(b"x" * 65)
    factory = Mock(return_value=process)
    monkeypatch.setattr(git_capture.shutil, "which", lambda _: sys.executable)
    monkeypatch.setattr(git_capture.subprocess, "Popen", factory)
    monkeypatch.setenv("MODEL_API_KEY", "private-value-not-for-git")
    monkeypatch.setenv("GIT_DIR", "attacker-directory")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "100")
    with pytest.raises(InspectionError) as exc:
        git_capture._run_git(tmp_path, ["diff", "--"], 64)
    assert exc.value.code == "git_output_too_large" and process.killed
    _, options = factory.call_args
    assert options["shell"] is False
    assert options["stdin"] == subprocess.DEVNULL
    assert not {"MODEL_API_KEY", "GIT_DIR", "GIT_CONFIG_COUNT"} & options["env"].keys()
    assert options["env"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert options["env"]["GIT_CONFIG_NOSYSTEM"] == "1"


def test_runner_accepts_exact_limit(monkeypatch, tmp_path):
    process = FakeProcess(b"x" * 64)
    monkeypatch.setattr(git_capture.shutil, "which", lambda _: sys.executable)
    monkeypatch.setattr(git_capture.subprocess, "Popen", lambda *args, **kwargs: process)
    assert git_capture._run_git(tmp_path, ["diff", "--"], 64) == (0, b"x" * 64)
    assert not process.killed


def test_runner_timeout_kills_git(monkeypatch, tmp_path):
    process = FakeProcess()

    class ExpiredTimer:
        def __init__(self, duration, callback):
            assert duration == 10
            self.callback = callback

        def start(self):
            self.callback()

        def cancel(self):
            pass

    monkeypatch.setattr(git_capture.shutil, "which", lambda _: sys.executable)
    monkeypatch.setattr(git_capture.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(git_capture.threading, "Timer", ExpiredTimer)
    with pytest.raises(InspectionError) as exc:
        git_capture._run_git(tmp_path, ["diff", "--"], 64)
    assert exc.value.code == "git_timeout" and process.killed


def test_missing_git(monkeypatch, tmp_path):
    monkeypatch.setattr(git_capture.shutil, "which", lambda _: None)
    with pytest.raises(InspectionError) as exc:
        git_capture._run_git(tmp_path, ["diff", "--"], 64)
    assert exc.value.code == "git_unavailable"


def test_git_executable_inside_repository_is_never_run(monkeypatch, tmp_path):
    program = tmp_path / "git.exe"
    program.write_bytes(b"not executed")
    monkeypatch.setattr(git_capture.shutil, "which", lambda _: str(program))
    factory = Mock(side_effect=AssertionError("No process should start"))
    monkeypatch.setattr(git_capture.subprocess, "Popen", factory)
    with pytest.raises(InspectionError) as exc:
        git_capture._run_git(tmp_path, ["diff", "--"], 64)
    assert exc.value.code == "unsafe_git_executable"
    factory.assert_not_called()
