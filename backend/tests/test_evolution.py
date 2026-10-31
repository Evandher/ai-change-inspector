import json
import sqlite3
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app import review_api, review_store
from app.feedback_models import FeedbackWrite
from app.inspection_models import RecoverableError
from tests.test_analysis import mock_meta as mock_meta
from tests.test_feedback import completed as completed
from tests.test_reviews import HEADERS, register, request
from tests.test_reviews import api as api
from tests.test_reviews import authorized_root as authorized_root


def child(api, root, parent):
    body = request(root).model_dump(mode="json")
    body["parent_review_id"] = parent
    result = api.post("/api/reviews", headers=HEADERS, json=body)
    assert result.status_code == 201
    return result.json()["review_id"]


@pytest.fixture
def family(api, authorized_root, completed):
    root = completed["review_id"]
    first = child(api, authorized_root, root)
    branch = child(api, authorized_root, root)
    grandchild = child(api, authorized_root, first)
    store = review_api.get_review_repository()
    store.claim(branch)
    store.finish(branch, None, RecoverableError(code="model_timeout", message="Provider failed"))
    store.claim(grandchild)
    store.save_feedback(
        root, 0, FeedbackWrite(decision="request_changes", comment="<script>test</script>")
    )
    return root, first, branch, grandchild


def test_timeline_navigates_ancestors_descendants_and_branches(api, family):
    root, first, branch, grandchild = family
    result = api.get(f"/api/reviews/{grandchild}/timeline")
    assert result.status_code == 200
    data = result.json()
    assert data["review_id"] == grandchild
    assert {item["review_id"] for item in data["items"]} == set(family)
    assert {item["status"] for item in data["items"]} == {
        "completed",
        "pending",
        "error",
        "analyzing",
    }
    assert [(item["created_at"], item["review_id"]) for item in data["items"]] == sorted(
        (item["created_at"], item["review_id"]) for item in data["items"]
    )
    parents = {item["review_id"]: item["parent_review_id"] for item in data["items"]}
    assert parents == {root: None, first: root, branch: root, grandchild: first}
    assert not data["incomplete"] and not data["truncated"]
    assert all("diff" not in item and "analysis" not in item for item in data["items"])


def test_comparison_uses_stored_content_and_cannot_mutate_or_call_provider(
    api, family, authorized_root, monkeypatch
):
    root, first, _, _ = family
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        before = list(db.iterdump())
    expected_parent = api.get(f"/api/reviews/{root}").json()
    expected_child = api.get(f"/api/reviews/{first}").json()
    (authorized_root / "a.txt").write_text("Different current repository content")
    forbidden = Mock(side_effect=AssertionError("No parsing, Git or provider allowed"))
    monkeypatch.setattr(review_api, "parse_diff", forbidden)
    monkeypatch.setattr(review_api, "analyze_parsed", forbidden)
    for left, right in ((root, first), (first, root)):
        response = api.get(f"/api/reviews/{left}/compare/{right}")
        assert response.status_code == 200
        assert response.json() == {"parent": expected_parent, "child": expected_child}
        assert response.json()["parent"]["feedback"][0]["comment"] == "<script>test</script>"
    assert api.get(f"/api/reviews/{root}/timeline").status_code == 200
    assert (
        api.put(f"/api/reviews/{root}/compare/{first}", headers=HEADERS, json={}).status_code == 405
    )
    assert api.post(f"/api/reviews/{root}/timeline", headers=HEADERS, json={}).status_code == 405
    forbidden.assert_not_called()
    with sqlite3.connect(store.path) as db:
        assert list(db.iterdump()) == before


@pytest.mark.parametrize("pair", [(0, 0), (0, 3), (1, 2)])
def test_only_direct_parent_child_comparison_is_supported(api, family, pair):
    left, right = (family[index] for index in pair)
    response = api.get(f"/api/reviews/{left}/compare/{right}")
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "comparison_not_related"
    )


def test_missing_and_invalid_review_ids(api, family):
    root = family[0]
    missing = str(uuid4())
    assert api.get(f"/api/reviews/{missing}/timeline").status_code == 404
    assert api.get(f"/api/reviews/{root}/compare/{missing}").status_code == 404
    assert api.get(f"/api/reviews/{missing}/compare/{root}").status_code == 404
    assert api.get("/api/reviews/not-a-uuid/timeline").status_code == 422
    assert api.get(f"/api/reviews/{root}/compare/not-a-uuid").status_code == 422


def test_timeline_reports_missing_relationships_without_fabricating_snapshots(api, family):
    missing = str(uuid4())
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        db.execute("INSERT INTO review_links VALUES (?,?)", (missing, family[0]))
    data = api.get(f"/api/reviews/{family[0]}/timeline").json()
    assert data["incomplete"] and data["missing_review_ids"] == [missing]
    assert missing not in {item["review_id"] for item in data["items"]}


def test_timeline_cycles_and_limits_are_bounded(api, family, monkeypatch):
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        db.execute("INSERT INTO review_links VALUES (?,?)", (family[0], family[3]))
    assert api.get(f"/api/reviews/{family[0]}/timeline").json()["incomplete"]
    monkeypatch.setattr(review_store, "TIMELINE_LIMIT", 3)
    limited = api.get(f"/api/reviews/{family[0]}/timeline").json()
    assert limited["truncated"] and len(limited["items"]) <= 3


def test_history_authorization_and_cross_repository_corruption(
    api, family, authorized_root, monkeypatch
):
    other = authorized_root.parent / "other"
    other.mkdir()
    monkeypatch.setenv(
        "INSPECTOR_REPOSITORIES", json.dumps({"project": str(authorized_root), "other": str(other)})
    )
    body = request(other).model_dump(mode="json")
    body["repository"] = "other"
    response = api.post("/api/reviews", headers=HEADERS, json=body)
    assert response.status_code == 201
    other_id = response.json()["review_id"]
    store = review_api.get_review_repository()
    with sqlite3.connect(store.path) as db:
        db.execute("INSERT INTO review_links VALUES (?,?)", (other_id, family[0]))
    result = api.get(f"/api/reviews/{family[0]}/timeline").json()
    assert result["incomplete"] and other_id not in {item["review_id"] for item in result["items"]}
    assert api.get(f"/api/reviews/{family[0]}/compare/{other_id}").status_code == 409
    monkeypatch.setenv("INSPECTOR_REPOSITORIES", "{}")
    assert api.get(f"/api/reviews/{family[0]}/timeline").status_code == 403
    assert api.get(f"/api/reviews/{family[0]}/compare/{family[1]}").status_code == 403


def test_empty_and_failed_analysis_remain_distinct_in_comparison(api, authorized_root, mock_meta):
    from tests.test_analysis import envelope

    install, _, _ = mock_meta
    install(envelope({"summary": "No findings", "findings": []}))
    root = register(api, authorized_root)["review_id"]
    api.post(f"/api/reviews/{root}/analyze", headers=HEADERS, json={})
    followup = child(api, authorized_root, root)
    install(status=503)
    api.post(f"/api/reviews/{followup}/analyze", headers=HEADERS, json={})
    data = api.get(f"/api/reviews/{root}/compare/{followup}").json()
    assert data["parent"]["analysis"]["findings"] == [] and data["parent"]["status"] == "completed"
    assert data["child"]["analysis"] is None and data["child"]["status"] == "error"
    assert data["child"]["error"]
