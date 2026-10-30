import json
import sqlite3
from uuid import uuid4

import httpx2
import pytest
from mcp import Client

from app import mcp_server, review_api
from app.feedback_models import FeedbackWrite
from app.mcp_server import create_server, inspect_repository, read_review_feedback
from app.review_store import ReviewRepository
from app.services import inbox_client
from app.services.git_capture import AuthorizedRepository
from tests.test_analysis import mock_meta as mock_meta
from tests.test_parser import SIMPLE
from tests.test_reviews import HEADERS, register, request
from tests.test_reviews import api as api
from tests.test_reviews import authorized_root as authorized_root

HUMAN = {**HEADERS, "Origin": "http://127.0.0.1:5173"}


@pytest.fixture
def completed(api, authorized_root, mock_meta):
    item = register(api, authorized_root)
    result = api.post(f"/api/reviews/{item['review_id']}/analyze", headers=HEADERS, json={})
    assert result.json()["status"] == "completed"
    return result.json()


@pytest.mark.parametrize("decision", ["request_changes", "accept_risk", "dismiss"])
def test_decisions_comments_persist_without_mutating_snapshot(api, completed, decision):
    identifier = completed["review_id"]
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        before = db.execute("SELECT * FROM reviews WHERE review_id=?", (identifier,)).fetchone()
    comment = "<script>untrusted()</script>\nPlease check this assumption."
    result = api.put(
        f"/api/reviews/{identifier}/feedback/0",
        headers=HUMAN,
        json={"decision": decision, "comment": comment},
    )
    assert result.status_code == 200
    item = result.json()
    assert item["decision"] == decision and item["comment"] == comment and item["updated_at"]
    fresh = ReviewRepository(store.path, store.web_base)
    assert fresh.get(identifier).feedback[0].comment == comment
    assert fresh.get(identifier).analysis.model_dump() == completed["analysis"]
    with sqlite3.connect(store.path) as db:
        assert (
            db.execute("SELECT * FROM reviews WHERE review_id=?", (identifier,)).fetchone()
            == before
        )
        assert db.execute("SELECT comment FROM human_comments").fetchone()[0] == comment
    feedback = api.get(f"/api/reviews/{identifier}/feedback").json()
    assert feedback["pending_count"] == 0
    assert feedback["items"][0]["finding"] == completed["analysis"]["findings"][0]


def test_pending_and_replace_comment_are_explicit(api, completed):
    url = f"/api/reviews/{completed['review_id']}/feedback"
    assert api.get(url).json()["pending_count"] == 1
    first = api.put(
        url + "/0", headers=HUMAN, json={"decision": "request_changes", "comment": "First"}
    )
    second = api.put(url + "/0", headers=HUMAN, json={"decision": "accept_risk"})
    assert second.json()["comment"] == ""
    assert second.json()["updated_at"] >= first.json()["updated_at"]
    assert api.get(url).json()["items"][0]["decision"] == "accept_risk"


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "approve"},
        {"decision": "resolved"},
        {"decision": None},
        {"decision": "dismiss", "comment": "x" * 4001},
        {"decision": "dismiss", "comment": 123},
        {"decision": "dismiss", "verified": True},
    ],
)
def test_invalid_decisions_or_comments_never_persist(api, completed, body):
    url = f"/api/reviews/{completed['review_id']}/feedback"
    assert api.put(url + "/0", headers=HUMAN, json=body).status_code == 422
    assert api.get(url).json()["pending_count"] == 1


@pytest.mark.parametrize(
    "headers",
    [HEADERS, {**HEADERS, "Origin": "http://evil.example"}, {"Origin": "http://127.0.0.1:5173"}],
)
def test_feedback_write_requires_local_browser_origin_and_marker(api, completed, headers):
    url = f"/api/reviews/{completed['review_id']}/feedback/0"
    assert api.put(url, headers=headers, json={"decision": "dismiss"}).status_code == 403


def test_feedback_validates_review_finding_state_and_authorization(
    api, authorized_root, completed, monkeypatch
):
    assert (
        api.put(
            f"/api/reviews/{completed['review_id']}/feedback/99",
            headers=HUMAN,
            json={"decision": "dismiss"},
        ).status_code
        == 404
    )
    pending = register(api, authorized_root)
    assert (
        api.put(
            f"/api/reviews/{pending['review_id']}/feedback/0",
            headers=HUMAN,
            json={"decision": "dismiss"},
        ).status_code
        == 409
    )
    assert api.get(f"/api/reviews/{uuid4()}/feedback").status_code == 404
    monkeypatch.setenv("INSPECTOR_REPOSITORIES", "{}")
    assert api.get(f"/api/reviews/{completed['review_id']}/feedback").status_code == 403
    assert (
        api.put(
            f"/api/reviews/{completed['review_id']}/feedback/0",
            headers=HUMAN,
            json={"decision": "dismiss"},
        ).status_code
        == 403
    )


def test_parent_links_are_atomic_and_immutable(api, authorized_root, completed, mock_meta):
    parent = completed["review_id"]
    body = request(authorized_root).model_dump(mode="json")
    body["parent_review_id"] = parent
    child = api.post("/api/reviews", headers=HEADERS, json=body)
    assert child.status_code == 201
    identifier = child.json()["review_id"]
    assert child.json()["parent_review_id"] == parent
    assert api.get(f"/api/reviews/{parent}").json()["child_review_ids"] == [identifier]
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 201
    body["parent_review_id"] = None
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 409
    assert len(mock_meta[1]) == 1  # Registration/linking never calls Meta.
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE review_links SET parent_id=child_id")


def test_missing_cross_repository_and_self_parent_are_rejected(
    api, authorized_root, completed, monkeypatch
):
    body = request(authorized_root).model_dump(mode="json")
    body["parent_review_id"] = str(uuid4())
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 404
    body["parent_review_id"] = completed["review_id"]
    body["review_id"] = completed["review_id"]
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 409
    other = authorized_root.parent / "other"
    other.mkdir()
    monkeypatch.setenv(
        "INSPECTOR_REPOSITORIES", json.dumps({"project": str(authorized_root), "other": str(other)})
    )
    body.update(review_id=str(uuid4()), repository="other", repository_root=str(other))
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 409
    assert api.get("/api/reviews").json()["total"] == 1


@pytest.fixture
def bridge(api, authorized_root, monkeypatch):
    calls = []
    original = httpx2.Client

    def handler(request):
        calls.append(request.method)
        response = api.request(
            request.method, str(request.url), content=request.content, headers=dict(request.headers)
        )
        return httpx2.Response(response.status_code, content=response.content)

    monkeypatch.setattr(
        inbox_client,
        "HttpClient",
        lambda **options: original(**options, transport=httpx2.MockTransport(handler)),
    )
    return {"project": AuthorizedRepository("project", authorized_root)}, calls


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_feedback_is_read_only_and_parent_submission_works(
    bridge, completed, mock_meta, monkeypatch
):
    repositories, methods = bridge
    monkeypatch.setattr(mcp_server, "capture_changes", lambda *args: SIMPLE)
    async with Client(create_server(repositories), raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert set(tools) == {"inspect_changes", "get_review_feedback"}
        assert tools["get_review_feedback"].annotations.read_only_hint is True
        result = await client.call_tool(
            "get_review_feedback", {"repository": "project", "review_id": completed["review_id"]}
        )
        assert result.structured_content["status"] == "available"
        assert result.structured_content["feedback"]["pending_count"] == 1
        assert methods == ["GET"] and len(mock_meta[1]) == 1
        invalid = await client.call_tool(
            "get_review_feedback",
            {"repository": "project", "review_id": completed["review_id"], "decision": "dismiss"},
        )
        # SDK ignores extra tool arguments; they must never become a write operation.
        assert invalid.structured_content["feedback"]["items"][0]["decision"] is None
        child = await client.call_tool(
            "inspect_changes",
            {
                "repository": "project",
                "scope": "unstaged",
                "parent_review_id": completed["review_id"],
            },
        )
        assert child.structured_content["status"] == "completed"
        identifier = child.structured_content["review_id"]
        feedback = await client.call_tool(
            "get_review_feedback", {"repository": "project", "review_id": identifier}
        )
        assert feedback.structured_content["feedback"]["parent_review_id"] == completed["review_id"]
        assert len(mock_meta[1]) == 2 and "PUT" not in methods and "DELETE" not in methods


def test_feedback_errors_are_recoverable_and_do_not_leak(api, completed, bridge, monkeypatch):
    repositories, methods = bridge
    result = read_review_feedback(
        repositories, "unknown", completed["review_id"], "http://127.0.0.1:8000"
    )
    assert result.status == "blocked" and not methods
    result = read_review_feedback(repositories, "project", str(uuid4()), "http://127.0.0.1:8000")
    assert result.error.code == "review_not_found" and result.error.recoverable

    def offline(*args, **kwargs):
        raise httpx2.ConnectError("sensitive internal detail")

    monkeypatch.setattr(inbox_client, "HttpClient", offline)
    result = read_review_feedback(
        repositories, "project", completed["review_id"], "http://127.0.0.1:8000"
    )
    assert result.status == "error" and result.error.recoverable
    assert "sensitive" not in result.error.message


def test_old_database_tables_are_added_without_rewriting_reviews(api, completed):
    store = review_api.get_review_repository()
    identifier = completed["review_id"]
    with sqlite3.connect(store.path) as db:
        before = db.execute("SELECT * FROM reviews").fetchall()
        for table in ("human_comments", "human_decisions", "review_links"):
            db.execute(f"DROP TABLE {table}")  # Fixed test-only names in an isolated database.
    restored = ReviewRepository(store.path, store.web_base)
    assert restored.get(identifier).feedback == []
    restored.save_feedback(identifier, 0, FeedbackWrite(decision="dismiss", comment="Preserved"))
    again = ReviewRepository(store.path, store.web_base)
    assert again.feedback(identifier).items[0].comment == "Preserved"
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT * FROM reviews").fetchall() == before


def test_agent_reads_saved_comments_without_authoring_decisions(api, completed, bridge, mock_meta):
    repositories, methods = bridge
    identifier = completed["review_id"]
    api.put(
        f"/api/reviews/{identifier}/feedback/0",
        headers=HUMAN,
        json={
            "decision": "request_changes",
            "comment": "Add a boundary test; do not run automatically.",
        },
    )
    result = read_review_feedback(repositories, "project", identifier, "http://127.0.0.1:8000")
    assert result.feedback.items[0].decision == "request_changes"
    assert result.feedback.items[0].comment.startswith("Add a boundary test")
    assert result.feedback.items[0].updated_at
    assert methods == ["GET"] and len(mock_meta[1]) == 1
    wrong = {"project": AuthorizedRepository("project", repositories["project"].root.parent)}
    assert (
        read_review_feedback(wrong, "project", identifier, "http://127.0.0.1:8000").status
        == "blocked"
    )


def test_invalid_parent_is_rejected_even_before_git_capture(
    completed, bridge, monkeypatch, mock_meta
):
    repositories, _ = bridge

    def no_git(*args):
        raise AssertionError("Must reject parent before Git")

    monkeypatch.setattr(mcp_server, "capture_changes", no_git)
    result = inspect_repository(
        repositories, "project", "unstaged", "http://127.0.0.1:8000", str(uuid4())
    )
    assert result.status == "error" and result.error.code == "review_not_found"
    assert len(mock_meta[1]) == 1


def test_empty_and_failed_analyses_have_no_feedback_items(api, authorized_root, mock_meta):
    from tests.test_analysis import envelope

    install, _, _ = mock_meta
    install(envelope({"summary": "No findings", "findings": []}))
    empty = register(api, authorized_root)["review_id"]
    api.post(f"/api/reviews/{empty}/analyze", headers=HEADERS, json={})
    data = api.get(f"/api/reviews/{empty}/feedback").json()
    assert data["analysis_status"] == "completed" and data["items"] == []
    assert (
        api.put(
            f"/api/reviews/{empty}/feedback/0", headers=HUMAN, json={"decision": "dismiss"}
        ).status_code
        == 404
    )
    install(status=503)
    failed = register(api, authorized_root)["review_id"]
    api.post(f"/api/reviews/{failed}/analyze", headers=HEADERS, json={})
    assert api.get(f"/api/reviews/{failed}/feedback").json()["analysis_status"] == "error"
    assert (
        api.put(
            f"/api/reviews/{failed}/feedback/0", headers=HUMAN, json={"decision": "dismiss"}
        ).status_code
        == 409
    )
