import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from app import mcp_server
from app.inspection_models import InspectionError
from app.mcp_server import create_server, inspect_repository, load_key_file
from app.services.diff_parser import DiffParseError
from app.services.git_capture import AuthorizedRepository
from tests import test_analysis
from tests.test_analysis import envelope
from tests.test_parser import SIMPLE

mock_meta = test_analysis.mock_meta


@pytest.fixture
def repositories(tmp_path):
    return {"project": AuthorizedRepository("project", tmp_path.resolve())}


@pytest.fixture
def captured(monkeypatch):
    capture = Mock(return_value=SIMPLE)
    monkeypatch.setattr(mcp_server, "capture_changes", capture)
    return capture


def test_unauthorized_id_never_reads_git_or_calls_provider(repositories, captured):
    result = inspect_repository(repositories, "unknown", "unstaged")
    assert result.status == "blocked" and result.error.code == "unauthorized_repository"
    assert result.analysis is None
    captured.assert_not_called()


def test_no_changes_skips_parser_and_model(repositories, captured, monkeypatch):
    captured.return_value = ""
    parser = Mock(side_effect=AssertionError("Parser must not run"))
    monkeypatch.setattr(mcp_server, "parse_diff", parser)
    result = inspect_repository(repositories, "project", "staged")
    assert result.status == "no_changes" and result.analysis is None and result.error is None
    assert result.untracked_policy == "excluded"
    parser.assert_not_called()


def test_complete_mcp_audit_reuses_sdk_and_backend_checks(repositories, captured, mock_meta):
    _, calls, _ = mock_meta
    result = inspect_repository(repositories, "project", "unstaged")
    assert result.status == "completed"
    assert result.analysis.findings[0].all_references_valid is True
    assert result.analysis.findings[0].reference_checks[0].reason == "matched"
    assert result.analysis.findings[0].hypothesis.suggested_tests
    assert len(calls) == 1
    captured.assert_called_once_with(repositories["project"], "unstaged")


def test_invalid_provider_reference_stays_unverified(repositories, captured, mock_meta):
    install, _, _ = mock_meta
    response = envelope()
    review = json.loads(response["output"][0]["content"][0]["text"])
    review["findings"][0]["references"][0]["file_id"] = "invented"
    response["output"][0]["content"][0]["text"] = json.dumps(review)
    install(response)
    result = inspect_repository(repositories, "project", "staged")
    assert result.status == "completed"
    finding = result.analysis.findings[0]
    assert finding.all_references_valid is False
    assert finding.reference_checks[0].reason == "file_not_found"
    assert "resolved" not in result.model_dump_json()


@pytest.mark.parametrize(
    "text",
    [
        SIMPLE.replace("a.txt", ".env"),
        SIMPLE.replace("+new", '+api_key = "sensitive-value-12345"'),
    ],
)
def test_filters_block_before_any_meta_call(repositories, captured, mock_meta, text):
    _, calls, _ = mock_meta
    captured.return_value = text
    result = inspect_repository(repositories, "project", "unstaged")
    assert result.status == "blocked" and result.analysis is None
    assert result.error.code in {"sensitive_path", "possible_secret"}
    assert "sensitive-value-12345" not in result.model_dump_json()
    assert calls == []


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (InspectionError("git_timeout", "Safe timeout"), "git_timeout"),
        (DiffParseError("invalid_hunk", "Safe parser error", 4), "invalid_hunk"),
    ],
)
def test_capture_and_parser_failures_are_structured(repositories, captured, error, code):
    captured.side_effect = error
    result = inspect_repository(repositories, "project", "unstaged")
    assert result.status == "error" and result.error.code == code
    assert result.error.recoverable and result.analysis is None


def test_provider_failure_is_structured(repositories, captured, mock_meta):
    install, calls, _ = mock_meta
    install({"error": {"message": "do-not-expose", "type": "error"}}, status=429)
    result = inspect_repository(repositories, "project", "staged")
    assert result.status == "error" and result.error.code == "model_rate_limited"
    assert result.error.recoverable and result.analysis is None
    assert "do-not-expose" not in result.model_dump_json()
    assert len(calls) == 1


def test_oversized_analysis_is_recoverable_without_meta(repositories, captured, mock_meta):
    _, calls, _ = mock_meta
    captured.return_value = SIMPLE.replace("+new", "+" + "x" * (128 * 1024))
    result = inspect_repository(repositories, "project", "unstaged")
    assert result.status == "error" and result.error.code == "analysis_too_large"
    assert calls == []


def test_unexpected_error_does_not_expose_internal_details(repositories, captured):
    captured.side_effect = RuntimeError("private-internal-value")
    result = inspect_repository(repositories, "project", "unstaged")
    assert result.error.code == "inspection_failed"
    assert "private-internal-value" not in result.model_dump_json()


def test_key_file_only_loads_key_without_variable_expansion(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("EXPAND_ME", "do-not-expand")
    monkeypatch.delenv("GIT_DIR", raising=False)
    path = tmp_path / ".env"
    path.write_text('MODEL_API_KEY="${EXPAND_ME}"\nGIT_DIR=attacker\n', encoding="utf-8")
    load_key_file(path)
    import os

    assert os.environ["MODEL_API_KEY"] == "${EXPAND_ME}"
    assert "GIT_DIR" not in os.environ
    monkeypatch.setenv("MODEL_API_KEY", "already-configured")
    load_key_file(path)
    assert os.environ["MODEL_API_KEY"] == "already-configured"
    for invalid in (Path("relative.env"), tmp_path / "absent.env"):
        with pytest.raises(ValueError):
            load_key_file(invalid)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_tool_discovery_structured_output_and_explicit_scope(
    repositories,
    captured,
    mock_meta,
):
    async with Client(create_server(repositories), raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert [tool.name for tool in tools] == ["inspect_changes"]
        tool = tools[0]
        assert set(tool.input_schema["required"]) == {"repository", "scope"}
        assert tool.input_schema["properties"]["scope"]["enum"] == ["staged", "unstaged"]
        assert tool.output_schema is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.idempotent_hint is False
        result = await client.call_tool(
            "inspect_changes", {"repository": "project", "scope": "unstaged"}
        )
        assert not result.is_error
        assert result.structured_content["status"] == "completed"
        checks = result.structured_content["analysis"]["findings"][0]["reference_checks"]
        assert checks[0]["status"] == "valid"
        for arguments in (
            {"repository": "project"},
            {"repository": "project", "scope": "all"},
            {"repository": "../../outside", "scope": "staged"},
        ):
            invalid = await client.call_tool("inspect_changes", arguments)
            assert invalid.is_error


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_real_stdio_protocol_from_an_unrelated_working_directory(tmp_path, mode):
    # No repository commands, keys or model calls: verify stdio discovery and safe errors.
    launcher = Path(__file__).resolve().parents[1] / "run_mcp.py"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(launcher), "--repo", f"project={tmp_path}"],
        cwd=tmp_path,
        env={"MODEL_API_KEY": ""},
    )
    async with Client(parameters, read_timeout_seconds=20, mode=mode) as client:
        tools = (await client.list_tools()).tools
        assert [tool.name for tool in tools] == ["inspect_changes"]
        result = await client.call_tool(
            "inspect_changes", {"repository": "unknown", "scope": "unstaged"}
        )
        assert not result.is_error
        assert result.structured_content["status"] == "blocked"
        result = await client.call_tool(
            "inspect_changes", {"repository": "project", "scope": "staged"}
        )
        assert result.structured_content["error"]["code"] == "invalid_repository"
