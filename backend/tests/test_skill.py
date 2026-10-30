"""Static packaging and live MCP-schema checks; never audit a repository or call Meta."""

import json
import re
from pathlib import Path
from typing import get_args
from unittest.mock import Mock

import pytest
from mcp import Client

from app.feedback_models import Decision, FeedbackResult
from app.inspection_models import InspectionResult, RecoverableError
from app.mcp_server import create_server
from app.services import git_capture
from app.services.git_capture import AuthorizedRepository

SKILL = Path(__file__).resolve().parents[2] / "skills/ai-change-inspector"
EXAMPLES = json.loads((SKILL / "references/examples.json").read_text(encoding="utf-8"))


def text_and_metadata():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    opening, header, body = text.split("---", 2)
    assert opening == ""
    # Deliberately support only the two plain, single-line YAML scalars we ship.
    entries = [line.partition(": ") for line in header.strip().splitlines()]
    assert all(separator and value.strip() for _, separator, value in entries)
    metadata = {key: value for key, _, value in entries}
    assert len(metadata) == len(entries)
    return metadata, body


def test_portable_skill_metadata_has_no_host_extensions_or_permissions():
    metadata, body = text_and_metadata()
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"])
    assert len(metadata["name"]) < 64 and len(metadata["description"]) <= 1024
    assert "<" not in metadata["description"] and ">" not in metadata["description"]
    assert not re.search(r"!`|\$ARGUMENTS|\$\{CLAUDE_SKILL_DIR\}", body)
    assert {item.relative_to(SKILL).as_posix() for item in SKILL.rglob("*") if item.is_file()} == {
        "SKILL.md",
        "references/examples.json",
    }


def test_references_resolve_inside_portable_bundle_without_private_paths():
    _, body = text_and_metadata()
    links = re.findall(r"\]\(([^)]+)\)", body)
    assert links
    for link in links:
        target = (SKILL / link).resolve()
        assert target.is_relative_to(SKILL.resolve()) and target.is_file()
    for path in SKILL.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"[A-Za-z]:[\\/]|/(?:Users|home)/[^/\s]+|\\\\[^\s]+", text)
            assert not re.search(r"(?:MODEL_API_KEY|api_key)\s*[:=]\s*[\w-]+", text)


def matrix(body, heading):
    section = body.split(f"| {heading} |", 1)[1].split("\n\n", 1)[0]
    return set(re.findall(r"^\| `([a-z_]+)` \|", section, re.MULTILINE))


def test_status_and_decision_tables_cover_actual_backend_contracts():
    _, body = text_and_metadata()
    assert matrix(body, "status") == set(
        get_args(InspectionResult.model_fields["status"].annotation)
    )
    assert matrix(body, "feedback status") == set(
        get_args(FeedbackResult.model_fields["status"].annotation)
    )
    assert matrix(body, "decision") == set(get_args(Decision))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example["name"])
async def test_documented_calls_route_through_real_mcp_contract_without_side_effects(
    example, monkeypatch, tmp_path
):
    from app import mcp_server

    assert set(example) == {"name", "developer_request", "tool", "arguments"}
    assert example["developer_request"]
    audit = Mock(
        side_effect=lambda repos, repository, scope, endpoint, parent=None: InspectionResult(
            status="no_changes", repository=repository, scope=scope
        )
    )
    lookup = Mock(
        side_effect=lambda repos, repository, review_id, endpoint: FeedbackResult(
            status="error",
            repository=repository,
            review_id=review_id,
            error=RecoverableError(code="web_service_unavailable", message="Mock offline"),
        )
    )
    monkeypatch.setattr(mcp_server, "inspect_repository", audit)
    monkeypatch.setattr(mcp_server, "read_review_feedback", lookup)
    monkeypatch.setattr(
        git_capture, "capture_changes", Mock(side_effect=AssertionError("No Git permitted"))
    )
    repository = AuthorizedRepository("project", tmp_path.resolve())
    async with Client(create_server({"project": repository}), raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert example["tool"] in tools
        args = example["arguments"]
        schema = tools[example["tool"]].input_schema
        assert set(schema.get("required", [])) <= args.keys() <= schema["properties"].keys()
        result = await client.call_tool(example["tool"], args)
        assert not result.is_error
    if example["tool"] == "inspect_changes":
        audit.assert_called_once_with(
            {"project": repository},
            args["repository"],
            args["scope"],
            "http://127.0.0.1:8000",
            args.get("parent_review_id"),
        )
        lookup.assert_not_called()
    else:
        lookup.assert_called_once_with(
            {"project": repository}, args["repository"], args["review_id"], "http://127.0.0.1:8000"
        )
        audit.assert_not_called()
