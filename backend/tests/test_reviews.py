import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from app import review_api
from app.local_settings import loopback_url
from app.main import app
from app.models import ParseResponse
from app.review_models import ReviewCreate, ReviewError
from app.review_store import ReviewRepository
from app.services import inbox_client
from app.services.diff_parser import parse_diff
from app.services.git_capture import AuthorizedRepository
from tests import test_analysis
from tests.test_analysis import envelope
from tests.test_parser import SIMPLE

mock_meta = test_analysis.mock_meta
HEADERS = {"X-Inspector-Request": "1"}


@pytest.fixture
def authorized_root(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setenv("INSPECTOR_REPOSITORIES", json.dumps({"project": str(root.resolve())}))
    return root.resolve()


@pytest.fixture
def api(authorized_root):
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        yield client


def request(root, diff=SIMPLE, identifier=None):
    return ReviewCreate(
        review_id=identifier or uuid4(),
        repository="project",
        repository_root=str(root),
        scope="unstaged",
        diff=diff,
    )


def register(api, root, diff=SIMPLE, identifier=None):
    response = api.post(
        "/api/reviews",
        headers=HEADERS,
        json=request(root, diff, identifier).model_dump(mode="json"),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_snapshot_survives_repository_and_service_changes(tmp_path, authorized_root):
    path = tmp_path / "saved.sqlite3"
    store = ReviewRepository(path, "http://127.0.0.1:5173")
    text = SIMPLE.replace("\n", "\r\n")
    body = request(authorized_root, text)
    parsed = ParseResponse.model_validate(asdict(parse_diff(text)))
    snapshot = store.create(body, parsed)
    assert UUID(snapshot.review_id).version == 4
    assert snapshot.status == "pending" and snapshot.origin == "mcp"
    assert snapshot.diff_sha256 == hashlib.sha256(text.encode()).hexdigest()
    (authorized_root / "a.txt").write_text("a completely different file")
    restored = ReviewRepository(path, "http://127.0.0.1:5173").get(snapshot.review_id)
    assert restored.diff == text
    assert restored.parsed_diff == parsed
    assert restored.created_at == snapshot.created_at
    assert restored.review_url.endswith(snapshot.review_id)
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable snapshot"):
            connection.execute("UPDATE reviews SET diff='changed'")


def test_idempotent_registration_and_conflicts(api, authorized_root):
    identifier = uuid4()
    first = register(api, authorized_root, identifier=identifier)
    second = register(api, authorized_root, identifier=identifier)
    assert first == second
    assert api.get("/api/reviews").json()["total"] == 1
    response = api.post(
        "/api/reviews",
        headers=HEADERS,
        json=request(authorized_root, SIMPLE.replace("+new", "+different"), identifier).model_dump(
            mode="json"
        ),
    )
    assert response.status_code == 409
    assert api.get(f"/api/reviews/{identifier}").json()["diff"] == SIMPLE


def test_concurrent_registration_and_claim_only_one_analysis(tmp_path, authorized_root):
    store = ReviewRepository(tmp_path / "concurrent.sqlite3", "http://127.0.0.1:5173")
    body = request(authorized_root)
    parsed = ParseResponse.model_validate(asdict(parse_diff(SIMPLE)))
    with ThreadPoolExecutor(max_workers=4) as executor:
        snapshots = list(executor.map(lambda _: store.create(body, parsed), range(4)))
    assert len({item.review_id for item in snapshots}) == 1
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims = list(executor.map(lambda _: store.claim(str(body.review_id)), range(4)))
    assert sum(claims) == 1


def test_registration_committed_before_model_call(api, authorized_root, mock_meta, monkeypatch):
    snapshot = register(api, authorized_root)
    assert snapshot["analysis"] is None and snapshot["status"] == "pending"
    _, calls, _ = mock_meta
    assert calls == []
    original = review_api.analyze_parsed

    def verify(parsed):
        persisted = review_api.get_review_repository().get(snapshot["review_id"])
        assert persisted.status == "analyzing" and persisted.diff == SIMPLE
        return original(parsed)

    monkeypatch.setattr(review_api, "analyze_parsed", verify)
    response = api.post(f"/api/reviews/{snapshot['review_id']}/analyze", headers=HEADERS, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed" and data["finished_at"]
    assert data["analysis"]["findings"][0]["all_references_valid"] is True
    again = api.post(f"/api/reviews/{snapshot['review_id']}/analyze", headers=HEADERS, json={})
    assert again.json() == data and len(calls) == 1


def test_completed_zero_findings_is_not_error(api, authorized_root, mock_meta):
    install, _, _ = mock_meta
    install(
        envelope({"summary": "No hay evidencia suficiente para proponer riesgos.", "findings": []})
    )
    snapshot = register(api, authorized_root)
    data = api.post(
        f"/api/reviews/{snapshot['review_id']}/analyze", headers=HEADERS, json={}
    ).json()
    assert data["status"] == "completed" and data["analysis"]["findings"] == []
    assert data["error"] is None


@pytest.mark.parametrize("failure", ["rate_limit", "incomplete", "malformed"])
def test_provider_failure_retains_diff_and_does_not_claim_success(
    api,
    authorized_root,
    mock_meta,
    failure,
):
    install, calls, _ = mock_meta
    if failure == "rate_limit":
        install({"error": {"message": "private-provider-body", "type": "error"}}, status=429)
    elif failure == "incomplete":
        install(envelope(status="incomplete"))
    else:
        install(envelope({"bad": "schema"}))
    snapshot = register(api, authorized_root)
    url = f"/api/reviews/{snapshot['review_id']}"
    data = api.post(url + "/analyze", headers=HEADERS, json={}).json()
    assert data["status"] == "error" and data["analysis"] is None
    assert data["error"]["recoverable"] and data["diff"] == SIMPLE
    assert "private-provider-body" not in json.dumps(data)
    assert api.get(url).json() == data
    api.post(url + "/analyze", headers=HEADERS, json={})
    assert len(calls) == 1


def test_restart_marks_interrupted_and_preserves_pending(authorized_root):
    store = review_api.get_review_repository()
    body = request(authorized_root)
    parsed = ParseResponse.model_validate(asdict(parse_diff(SIMPLE)))
    running = store.create(body, parsed)
    pending = store.create(request(authorized_root), parsed)
    assert store.claim(running.review_id)
    with TestClient(
        app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)
    ) as restarted:
        data = restarted.get(f"/api/reviews/{running.review_id}").json()
        assert data["status"] == "error" and data["error"]["code"] == "analysis_interrupted"
        assert data["diff"] == SIMPLE and data["analysis"] is None
        assert restarted.get(f"/api/reviews/{pending.review_id}").json()["status"] == "pending"


def test_listing_pagination_has_no_diff_content(api, authorized_root):
    for _ in range(3):
        register(api, authorized_root)
    page = api.get("/api/reviews?limit=2&offset=0").json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert all("diff" not in item and "analysis" not in item for item in page["items"])
    assert len(api.get("/api/reviews?limit=2&offset=2").json()["items"]) == 1
    assert api.get("/api/reviews?limit=1000").status_code == 422


def test_invalid_ids_and_unauthorized_repository_are_rejected(api, authorized_root, mock_meta):
    for identifier in ["not-a-uuid", "00000000-0000-0000-0000-000000000000"]:
        assert api.get(f"/api/reviews/{identifier}").status_code == 422
    assert api.get(f"/api/reviews/{uuid4()}").status_code == 404
    body = request(authorized_root).model_dump(mode="json")
    body["repository_root"] = str(authorized_root.parent)
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 403
    body["repository_root"] = str(authorized_root)
    body["diff"] = SIMPLE.replace("a.txt", ".env")
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 403
    assert api.get("/api/reviews").json()["total"] == 0
    assert mock_meta[1] == []


def test_caller_cannot_declare_analysis_status_or_overwrite_a_snapshot(api, authorized_root):
    body = request(authorized_root).model_dump(mode="json")
    body["status"] = "completed"
    assert api.post("/api/reviews", headers=HEADERS, json=body).status_code == 422
    assert api.get("/api/reviews").json()["total"] == 0
    snapshot = register(api, authorized_root)
    assert (
        api.put(
            f"/api/reviews/{snapshot['review_id']}", headers=HEADERS, json={"status": "completed"}
        ).status_code
        == 405
    )
    assert api.get(f"/api/reviews/{snapshot['review_id']}").json()["status"] == "pending"


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Host": "evil.example:8000"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "http://127.0.0.1:6666"},
    ],
)
def test_external_pages_cannot_read_or_write(api, authorized_root, headers):
    response = api.get("/api/reviews", headers=headers)
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
    response = api.post(
        "/api/reviews",
        headers={**HEADERS, **headers},
        json=request(authorized_root).model_dump(mode="json"),
    )
    assert response.status_code == 403


def test_simple_forms_preflight_and_non_loopback_peers_denied(api, authorized_root):
    assert (
        api.post(
            "/api/reviews",
            content="diff=anything",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ).status_code
        == 415
    )
    assert (
        api.post("/api/reviews", json=request(authorized_root).model_dump(mode="json")).status_code
        == 403
    )
    preflight = api.options(
        "/api/reviews",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 403
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("192.168.1.2", 50000)) as remote:
        assert remote.get("/api/reviews").status_code == 403
    assert api.get("/api/reviews").headers["cache-control"] == "no-store"


def test_broken_storage_is_sanitized(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not-a-database")
    with pytest.raises(ReviewError) as exc:
        ReviewRepository(path, "http://127.0.0.1:5173")
    assert exc.value.code == "storage_unavailable" and str(path) not in str(exc.value)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8000",
        "http://evil.example:8000",
        "http://192.168.1.1:8000",
        "http://127.0.0.1:8000/path",
        "http://user:pass@127.0.0.1:8000",
        "http://127.0.0.1:8000?q=x",
    ],
)
def test_mcp_cannot_submit_to_external_urls(url):
    with pytest.raises(ValueError):
        loopback_url(url)


def test_offline_web_returns_correlated_error_without_provider(tmp_path, monkeypatch):
    original = inbox_client.HttpClient
    attempts = []

    def offline(request):
        attempts.append(request)
        raise httpx2.ConnectError("private-network-error", request=request)

    monkeypatch.setattr(
        inbox_client,
        "HttpClient",
        lambda **options: original(
            **options,
            transport=httpx2.MockTransport(offline),
        ),
    )
    with pytest.raises(inbox_client.SubmissionError) as exc:
        inbox_client.submit_review(
            AuthorizedRepository("project", tmp_path), "unstaged", SIMPLE, "http://127.0.0.1:8000"
        )
    assert not exc.value.confirmed and UUID(exc.value.review_id).version == 4
    assert exc.value.review_url.endswith(exc.value.review_id)
    assert "private-network-error" not in str(exc.value)
    assert len(attempts) == 1
