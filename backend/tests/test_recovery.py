import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Event
from uuid import uuid4

import pytest

from app import review_api
from app.analysis_models import ModelReview
from app.provider_models import ProviderDiagnostic
from app.recovery_models import RecoveryRequest, RecoveryResult
from app.recovery_store import RecoveryStore
from app.review_models import ReviewError
from app.services import analysis, recovery
from app.services.diff_parser import parse_diff
from app.services.model_client import AnalysisError, review_diff
from app.services.output_budget import output_budget
from app.services.recovery_recipes import reconstruct_batches
from app.services.reference_validator import check_findings
from tests import test_analysis, test_reviews
from tests.test_analysis import envelope
from tests.test_large_audits import multi_file
from tests.test_parser import SIMPLE
from tests.test_reviews import HEADERS, register

mock_meta = test_analysis.mock_meta
api = test_reviews.api
authorized_root = test_reviews.authorized_root
HUMAN = {**HEADERS, "Origin": "http://127.0.0.1:5173"}


def body_for(parsed):
    file = parsed.files[0]
    hunk = file.hunks[0]
    line = next(line for line in hunk.lines if line.new_line is not None)
    return {
        "summary": "Synthetic completed batch",
        "findings": [
            {
                "title": "Risk in " + file.new_path,
                "severity": "high",
                "explanation": "Synthetic hypothesis",
                "references": [
                    {
                        "file_id": file.file_id,
                        "hunk_id": hunk.hunk_id,
                        "path": file.new_path,
                        "side": "new",
                        "line_start": line.new_line,
                        "line_end": line.new_line,
                        "quote": line.content,
                    }
                ],
                "suggested_tests": ["Do not execute synthetic suggestions"],
            }
        ],
    }


def partial_review(api, root, monkeypatch, three=False):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    count = 0

    def first_attempt(parsed, diagnostic):
        nonlocal count
        count += 1
        if count > 1:
            diagnostic.status, diagnostic.outcome = "incomplete", "budget"
            diagnostic.incomplete_reason = "max_output_tokens"
            raise AnalysisError("model_output_budget", "Synthetic incomplete batch")
        diagnostic.status, diagnostic.outcome = "completed", "completed"
        return ModelReview.model_validate(body_for(parsed))

    monkeypatch.setattr(analysis, "review_diff", first_attempt)
    text = multi_file()
    if three:
        text += SIMPLE.replace("a.txt", "third.txt").replace("+new", "+" + "z" * 2400)
    registered = register(api, root, text)
    result = api.post(
        f"/api/reviews/{registered['review_id']}/analyze", headers=HEADERS, json={}
    ).json()
    assert result["status"] == "error" and result["audit"]["status"] == "partial"
    return result


def command(data, batch_ids=None):
    return {
        "request_id": str(uuid4()),
        "batch_ids": batch_ids or ["batch-2"],
        "expected_version": data["recovery"]["version"],
        "expected_output_budget": data["recovery"].get("output_budget", 8192),
        "confirm_paid": True,
    }


def raw_review(identifier):
    with review_api.get_review_repository().connection() as c:
        return dict(c.execute("SELECT * FROM reviews WHERE review_id=?", (identifier,)).fetchone())


@pytest.mark.parametrize("budget", [16, 4096, 8192])
def test_output_budgets_are_sent_and_recorded(mock_meta, monkeypatch, budget):
    monkeypatch.setenv("INSPECTOR_MAX_OUTPUT_TOKENS", str(budget))
    _, calls, _ = mock_meta
    diagnostic = ProviderDiagnostic()
    review_diff(parse_diff(SIMPLE), diagnostic)
    assert diagnostic.max_output_tokens == budget
    assert json.loads(calls[0].content)["max_output_tokens"] == budget


@pytest.mark.parametrize("value", ["0", "15", "12288", "-1", "1.5", "none", ""])
def test_invalid_budgets_never_call_provider(mock_meta, monkeypatch, value):
    monkeypatch.setenv("INSPECTOR_MAX_OUTPUT_TOKENS", value)
    _, calls, _ = mock_meta
    with pytest.raises(AnalysisError) as exc:
        review_diff(parse_diff(SIMPLE))
    assert exc.value.code == "invalid_output_budget" and not calls


def test_default_budget_and_validated_ceiling(monkeypatch):
    monkeypatch.delenv("INSPECTOR_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("INSPECTOR_OUTPUT_TOKEN_CEILING", raising=False)
    assert output_budget() == 8192
    monkeypatch.setenv("INSPECTOR_OUTPUT_TOKEN_CEILING", "4096")
    with pytest.raises(AnalysisError):
        output_budget()
    monkeypatch.setenv("INSPECTOR_MAX_OUTPUT_TOKENS", "4096")
    assert output_budget() == 4096
    monkeypatch.setenv("INSPECTOR_OUTPUT_TOKEN_CEILING", "12288")
    with pytest.raises(AnalysisError):
        output_budget()


def test_selective_recovery_preserves_originals_and_feedback(
    api, authorized_root, monkeypatch, mock_meta
):
    initial = partial_review(api, authorized_root, monkeypatch)
    identifier = initial["review_id"]
    url = f"/api/reviews/{identifier}"
    saved = api.put(
        url + "/feedback/0",
        headers=HUMAN,
        json={"decision": "request_changes", "comment": "Keep this decision"},
    )
    assert saved.status_code == 200
    before = raw_review(identifier)
    store = review_api.get_review_repository()
    original = store.get(identifier, include_recovery=False)
    _, groups = reconstruct_batches(original)
    install, calls, _ = mock_meta
    install(envelope(body_for(groups["batch-2"])))
    request = command(initial)
    response = api.post(url + "/recovery", headers=HUMAN, json=request)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "completed" and data["audit"]["status"] == "completed"
    assert data["audit"]["unanalyzed_hunk_ids"] == []
    assert len(data["analysis"]["findings"]) == 2 and len(calls) == 1
    assert (
        data["analysis"]["findings"][0]["hypothesis"]
        == initial["analysis"]["findings"][0]["hypothesis"]
    )
    assert data["analysis"]["findings"][0]["attempt_ids"] == ["initial:batch-1"]
    attempt = data["recovery"]["attempts"][0]
    assert attempt["number"] == 2 and attempt["status"] == "completed"
    assert data["analysis"]["findings"][1]["attempt_ids"] == [attempt["attempt_id"]]
    assert all(f["all_references_valid"] for f in data["analysis"]["findings"])
    assert data["parsed_diff"] == initial["parsed_diff"]
    assert data["feedback"][0]["comment"] == "Keep this decision"
    assert raw_review(identifier) == before
    assert api.post(url + "/recovery", headers=HUMAN, json=request).json() == data
    assert api.post(url + "/analyze", headers=HEADERS, json={}).json() == data
    assert len(calls) == 1
    assert api.get("/api/reviews?status=completed&severity=high").json()["total"] == 1
    assert api.get(url + "/timeline").json()["items"][0]["status"] == "completed"


def test_one_of_two_incomplete_batches_remains_partial(
    api, authorized_root, monkeypatch, mock_meta
):
    initial = partial_review(api, authorized_root, monkeypatch, three=True)
    original = review_api.get_review_repository().get(initial["review_id"], include_recovery=False)
    _, groups = reconstruct_batches(original)
    install, calls, _ = mock_meta
    install(envelope(body_for(groups["batch-2"])))
    data = api.post(
        f"/api/reviews/{initial['review_id']}/recovery", headers=HUMAN, json=command(initial)
    ).json()
    assert data["status"] == "error" and data["audit"]["status"] == "partial"
    assert len(data["audit"]["completed_hunk_ids"]) == 2
    assert len(data["audit"]["unanalyzed_hunk_ids"]) == 1 and len(calls) == 1
    assert data["recovery"]["eligible_batch_ids"] == ["batch-3"]


def test_provider_errors_attempt_history_and_limits(api, authorized_root, monkeypatch, mock_meta):
    data = partial_review(api, authorized_root, monkeypatch)
    identifier = data["review_id"]
    install, calls, _ = mock_meta
    install(envelope(status="incomplete") | {"incomplete_details": {"reason": "max_output_tokens"}})
    first = command(data)
    data = api.post(f"/api/reviews/{identifier}/recovery", headers=HUMAN, json=first).json()
    assert data["recovery"]["attempts"][0]["status"] == "incomplete"
    assert (
        data["recovery"]["attempts"][0]["diagnostics"]["incomplete_reason"] == "max_output_tokens"
    )
    install({"error": {"message": "never store provider body", "type": "error"}}, status=500)
    data = api.post(f"/api/reviews/{identifier}/recovery", headers=HUMAN, json=command(data)).json()
    assert [a["number"] for a in data["recovery"]["attempts"]] == [2, 3]
    assert data["recovery"]["attempts"][1]["status"] == "failed"
    assert not data["recovery"]["eligible_batch_ids"]
    assert "never store" not in json.dumps(data)
    assert len(calls) == 2
    response = api.post(f"/api/reviews/{identifier}/recovery", headers=HUMAN, json=command(data))
    assert response.status_code == 409 and len(calls) == 2


def test_independent_validation_keeps_invalid_references(
    api, authorized_root, monkeypatch, mock_meta
):
    initial = partial_review(api, authorized_root, monkeypatch)
    install, _, _ = mock_meta
    wrong = body_for(parse_diff(SIMPLE))
    install(envelope(wrong))
    data = api.post(
        f"/api/reviews/{initial['review_id']}/recovery", headers=HUMAN, json=command(initial)
    ).json()
    finding = data["analysis"]["findings"][-1]
    assert not finding["all_references_valid"]
    assert finding["reference_checks"][0]["diff_line"] is None
    assert finding["hypothesis"]["references"] == wrong["findings"][0]["references"]


def test_origin_confirmation_eligibility_and_staleness(
    api, authorized_root, monkeypatch, mock_meta
):
    data = partial_review(api, authorized_root, monkeypatch)
    _, calls, _ = mock_meta
    url = f"/api/reviews/{data['review_id']}/recovery"
    request = command(data)
    assert api.post(url, headers=HEADERS, json=request).status_code == 403
    assert (
        api.post(url, headers={**HUMAN, "Origin": "http://evil.test"}, json=request).status_code
        == 403
    )
    assert api.post(url, headers={"Origin": HUMAN["Origin"]}, json=request).status_code == 403
    assert api.post(url, headers=HUMAN, json=request | {"confirm_paid": False}).status_code == 422
    assert (
        api.post(url, headers=HUMAN, json=request | {"batch_ids": ["batch-1"]}).status_code == 409
    )
    assert (
        api.post(
            url, headers=HUMAN, json=request | {"batch_ids": ["batch-2", "batch-2"]}
        ).status_code
        == 409
    )
    assert api.post(url, headers=HUMAN, json=request | {"expected_version": 99}).status_code == 409
    assert not calls


def test_historical_and_tampered_recipes_are_blocked(api, authorized_root, monkeypatch, mock_meta):
    legacy = register(api, authorized_root)
    assert (
        api.post(
            f"/api/reviews/{legacy['review_id']}/recovery",
            headers=HUMAN,
            json=command({"recovery": {"version": 0}}),
        ).status_code
        == 409
    )
    data = partial_review(api, authorized_root, monkeypatch)
    original = review_api.get_review_repository().get(data["review_id"], include_recovery=False)
    for mutation in ("size", "hunk", "coverage", "hash"):
        broken = original.model_copy(deep=True)
        if mutation == "size":
            broken.audit.batches[1].payload_bytes += 1
        if mutation == "hunk":
            broken.audit.batches[1].hunk_ids = ["invented"]
        if mutation == "coverage":
            broken.audit.unanalyzed_hunk_ids = []
        if mutation == "hash":
            broken.diff_sha256 = "0" * 64
        with pytest.raises(ReviewError):
            reconstruct_batches(broken)


def test_duplicate_requests_and_concurrent_batch_execution(api, authorized_root, monkeypatch):
    data = partial_review(api, authorized_root, monkeypatch)
    identifier = data["review_id"]
    begun, release = Event(), Event()
    calls = []

    def slow(parsed, diagnostic, **kwargs):
        calls.append(parsed)
        begun.set()
        assert release.wait(5)
        diagnostic.outcome = "completed"
        return ModelReview.model_validate(body_for(parsed))

    monkeypatch.setattr(recovery, "review_diff", slow)
    request = command(data)
    url = f"/api/reviews/{identifier}/recovery"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(lambda: api.post(url, headers=HUMAN, json=request))
        assert begun.wait(5)
        duplicate = api.post(url, headers=HUMAN, json=request)
        assert duplicate.status_code == 200 and duplicate.json()["status"] == "analyzing"
        conflict = api.post(url, headers=HUMAN, json=command(data))
        assert conflict.status_code == 409
        release.set()
        assert first.result().json()["status"] == "completed"
    assert len(calls) == 1


def test_interruption_preserves_finished_attempt_and_never_resumes(
    api, authorized_root, monkeypatch
):
    data = partial_review(api, authorized_root, monkeypatch, three=True)
    repository = review_api.get_review_repository()
    original = repository.get(data["review_id"], include_recovery=False)
    store = RecoveryStore(repository)
    request = RecoveryRequest.model_validate(command(data, ["batch-2", "batch-3"]))
    assert store.admit(original, request)
    attempts, _ = store.rows(original.review_id)
    assert store.start(attempts[0]["attempt_id"])
    assert not store.start(attempts[0]["attempt_id"])
    parsed, groups = reconstruct_batches(original)
    checked = check_findings(parsed, ModelReview.model_validate(body_for(groups["batch-2"])))
    for finding in checked:
        finding.batch_ids = ["batch-2"]
        finding.attempt_ids = [attempts[0]["attempt_id"]]
    store.finish_attempt(
        attempts[0]["attempt_id"],
        "completed",
        ProviderDiagnostic(status="completed"),
        RecoveryResult(summary="Kept result", findings=checked),
    )
    repository.recover_interrupted()
    effective = repository.get(original.review_id)
    assert [a.status for a in effective.recovery.attempts] == ["completed", "interrupted"]
    assert effective.audit.status == "partial" and len(effective.audit.completed_hunk_ids) == 2
    assert effective.recovery.eligible_batch_ids == ["batch-3"]
    assert len(effective.analysis.findings) == 2
    assert (
        repository.get(original.review_id, include_recovery=False).model_dump()
        == original.model_dump()
    )


def test_review_reservation_limit(api, authorized_root, monkeypatch):
    data = partial_review(api, authorized_root, monkeypatch, three=True)
    monkeypatch.setenv("INSPECTOR_MAX_RECOVERIES_PER_REVIEW", "1")
    response = api.post(
        f"/api/reviews/{data['review_id']}/recovery",
        headers=HUMAN,
        json=command(data, ["batch-2", "batch-3"]),
    )
    assert response.status_code == 409
    assert not review_api.get_review_repository().get(data["review_id"]).recovery.attempts


def test_pending_batches_are_not_retried(api, authorized_root, monkeypatch, mock_meta):
    monkeypatch.setenv("INSPECTOR_MAX_AUDIT_REQUESTS", "1")
    data = partial_review(api, authorized_root, monkeypatch)
    assert data["audit"]["batches"][1]["status"] == "pending"
    assert not data["recovery"]["eligible_batch_ids"]
    _, calls, _ = mock_meta
    response = api.post(
        f"/api/reviews/{data['review_id']}/recovery", headers=HUMAN, json=command(data)
    )
    assert response.status_code == 409 and not calls


def test_changed_egress_policy_blocks_stored_content(api, authorized_root, monkeypatch, mock_meta):
    data = partial_review(api, authorized_root, monkeypatch)
    _, calls, _ = mock_meta
    # A newly configured fake key now matches stored text. The old snapshot must not bypass policy.
    monkeypatch.setenv("MODEL_API_KEY", "x" * 20)
    response = api.post(
        f"/api/reviews/{data['review_id']}/recovery", headers=HUMAN, json=command(data)
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "possible_secret"
    assert not calls
    assert not review_api.get_review_repository().get(data["review_id"]).recovery.attempts


def test_each_send_rechecks_authorization_without_git(api, authorized_root, monkeypatch):
    from app.services import git_capture

    data = partial_review(api, authorized_root, monkeypatch, three=True)
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Git recapture forbidden")

    def completed(parsed, diagnostic, **kwargs):
        calls.append(parsed)
        diagnostic.outcome = "completed"
        monkeypatch.setenv("INSPECTOR_REPOSITORIES", "{}")
        return ModelReview.model_validate(body_for(parsed))

    monkeypatch.setattr(git_capture, "capture_changes", forbidden)
    monkeypatch.setattr(recovery, "review_diff", completed)
    result = api.post(
        f"/api/reviews/{data['review_id']}/recovery",
        headers=HUMAN,
        json=command(data, ["batch-2", "batch-3"]),
    ).json()
    assert len(calls) == 1 and result["audit"]["status"] == "partial"
    assert [a["status"] for a in result["recovery"]["attempts"]] == ["completed", "failed"]
    assert result["recovery"]["attempts"][1]["error_code"] == "unauthorized_repository"


def test_schema_failure_is_persisted_without_partial_results(
    api, authorized_root, monkeypatch, mock_meta
):
    data = partial_review(api, authorized_root, monkeypatch)
    install, calls, _ = mock_meta
    install(envelope({"secret_partial_output": "Do not persist invalid content"}))
    result = api.post(
        f"/api/reviews/{data['review_id']}/recovery", headers=HUMAN, json=command(data)
    ).json()
    attempt = result["recovery"]["attempts"][0]
    assert attempt["error_code"] == "model_invalid_output"
    assert attempt["diagnostics"]["outcome"] == "schema" and len(calls) == 1
    assert len(result["analysis"]["findings"]) == 1
    with review_api.get_review_repository().connection() as c:
        stored = dict(c.execute("SELECT * FROM review_batch_attempts").fetchone())
    assert stored["result_json"] is None and "Do not persist" not in json.dumps(stored)


def test_stale_new_request_cannot_repeat_failed_work(api, authorized_root, monkeypatch, mock_meta):
    data = partial_review(api, authorized_root, monkeypatch)
    install, calls, _ = mock_meta
    install(envelope(status="incomplete"))
    url = f"/api/reviews/{data['review_id']}/recovery"
    original = command(data)
    assert api.post(url, headers=HUMAN, json=original).status_code == 200
    assert (
        api.post(url, headers=HUMAN, json=original | {"request_id": str(uuid4())}).status_code
        == 409
    )
    assert len(calls) == 1


def test_legacy_nine_one_recipe_without_hash_remains_recoverable(api, authorized_root, monkeypatch):
    data = partial_review(api, authorized_root, monkeypatch)
    original = review_api.get_review_repository().get(data["review_id"], include_recovery=False)
    for batch in original.audit.batches:
        batch.payload_sha256 = None
        batch.payload_version = None
    parsed, groups = reconstruct_batches(original)
    assert len(groups) == 2 and asdict(parsed) == asdict(parse_diff(original.diff))
    original.audit.batches[1].payload_sha256 = "0" * 64
    with pytest.raises(ReviewError):
        reconstruct_batches(original)


def test_recovery_and_original_terminal_records_are_immutable(
    api, authorized_root, monkeypatch, mock_meta
):
    data = partial_review(api, authorized_root, monkeypatch)
    install, _, _ = mock_meta
    install(envelope(status="incomplete"))
    api.post(f"/api/reviews/{data['review_id']}/recovery", headers=HUMAN, json=command(data))
    with sqlite3.connect(review_api.get_review_repository().path) as c:
        for sql in (
            "UPDATE review_batch_attempts SET error_code='changed'",
            "DELETE FROM review_batch_attempts",
            "UPDATE review_recovery_runs SET effective_status='completed'",
            "DELETE FROM review_recovery_runs",
            "UPDATE reviews SET status='pending'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                c.execute(sql)


def test_budget_change_requires_new_confirmation(api, authorized_root, monkeypatch, mock_meta):
    data = partial_review(api, authorized_root, monkeypatch)
    install, calls, _ = mock_meta
    request = command(data)
    monkeypatch.setenv("INSPECTOR_MAX_OUTPUT_TOKENS", "4096")
    url = f"/api/reviews/{data['review_id']}"
    assert api.post(url + "/recovery", headers=HUMAN, json=request).status_code == 409
    assert not calls
    refreshed = api.get(url).json()
    original = review_api.get_review_repository().get(data["review_id"], include_recovery=False)
    _, groups = reconstruct_batches(original)
    install(envelope(body_for(groups["batch-2"])))
    result = api.post(url + "/recovery", headers=HUMAN, json=command(refreshed)).json()
    assert result["recovery"]["attempts"][0]["output_budget"] == 4096
    assert result["recovery"]["attempts"][0]["diagnostics"]["max_output_tokens"] == 4096
    assert json.loads(calls[0].content)["max_output_tokens"] == 4096


def test_additive_migration_of_actual_nine_one_shape(api, authorized_root, monkeypatch, tmp_path):
    from app.review_store import SCHEMA, ReviewRepository

    data = partial_review(api, authorized_root, monkeypatch)
    raw = raw_review(data["review_id"])
    path = tmp_path / "nine-one.sqlite3"
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        for column in ("agent_source", "coverage_json", "audit_json"):
            c.execute(f"ALTER TABLE reviews ADD COLUMN {column} TEXT")
        columns = list(raw)
        c.execute(
            "INSERT INTO reviews("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            list(raw.values()),
        )
        before = c.execute("SELECT * FROM reviews").fetchone()
    repository = ReviewRepository(path, "http://127.0.0.1:5173")
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT * FROM reviews").fetchone() == before
        assert c.execute("SELECT count(*) FROM review_batch_attempts").fetchone()[0] == 0
    assert repository.get(data["review_id"]).recovery.eligible_batch_ids == ["batch-2"]
