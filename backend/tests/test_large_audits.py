import json
import sqlite3
from dataclasses import asdict

import httpx2
import pytest
from openai import OpenAI

from app.analysis_models import ModelReview
from app.provider_models import ProviderDiagnostic
from app.review_store import ReviewRepository
from app.services import analysis, model_client
from app.services.audit_batches import audit_progress, plan_batches
from app.services.diff_parser import parse_diff
from app.services.model_client import AnalysisError, review_diff
from app.services.model_payload import model_payload, original_payload
from tests import test_analysis, test_reviews
from tests.test_analysis import envelope, review_body
from tests.test_parser import SIMPLE
from tests.test_reviews import HEADERS, register

mock_meta = test_analysis.mock_meta
api = test_reviews.api
authorized_root = test_reviews.authorized_root


def test_request_correlation_and_sensitive_metadata_filtering(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-secret-never-store")
    body = envelope()
    body["id"] = "test-secret-never-store"

    def factory(**kwargs):
        return OpenAI(
            **kwargs,
            http_client=httpx2.Client(
                transport=httpx2.MockTransport(
                    lambda request: httpx2.Response(
                        200, json=body, headers={"x-request-id": "req_mock"}
                    )
                )
            ),
        )

    monkeypatch.setattr(model_client, "OpenAI", factory)
    diagnostic = ProviderDiagnostic()
    review_diff(parse_diff(SIMPLE), diagnostic)
    assert diagnostic.request_id == "req_mock" and diagnostic.response_id is None
    assert "test-secret-never-store" not in diagnostic.model_dump_json()


@pytest.mark.parametrize(
    ("status", "reason", "code", "outcome"),
    [
        ("incomplete", "max_output_tokens", "model_output_budget", "budget"),
        ("incomplete", "content_filter", "model_incomplete", "incomplete"),
        ("incomplete", None, "model_incomplete", "incomplete"),
        ("failed", None, "model_provider_error", "provider"),
    ],
)
def test_diagnostics_do_not_infer_or_retain_partial_output(
    mock_meta, status, reason, code, outcome
):
    install, calls, _ = mock_meta
    body = envelope(status=status)
    body["incomplete_details"] = {"reason": reason} if reason else None
    body["usage"] = {
        "input_tokens": 2000,
        "output_tokens": 8192,
        "total_tokens": 10192,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 7000},
    }
    install(body)
    diagnostic = ProviderDiagnostic()
    with pytest.raises(AnalysisError) as exc:
        review_diff(parse_diff(SIMPLE), diagnostic)
    assert exc.value.code == code and diagnostic.outcome == outcome
    assert diagnostic.status == status and diagnostic.incomplete_reason == reason
    assert diagnostic.incomplete_details == ({"reason": reason} if reason else None)
    assert diagnostic.response_id == "resp_mock"
    assert (diagnostic.input_tokens, diagnostic.output_tokens, diagnostic.reasoning_tokens) == (
        2000,
        8192,
        7000,
    )
    assert "Posible cambio" not in diagnostic.model_dump_json()
    assert "fake-key" not in diagnostic.model_dump_json() and len(calls) == 1


def test_success_and_schema_failure_keep_usage_absence_explicit(mock_meta):
    install, _, _ = mock_meta
    diagnostic = ProviderDiagnostic()
    review_diff(parse_diff(SIMPLE), diagnostic)
    assert diagnostic.status == "completed" and diagnostic.outcome == "completed"
    assert diagnostic.input_tokens is None and diagnostic.request_id is None
    install(envelope({"wrong": "schema"}))
    with pytest.raises(AnalysisError) as exc:
        review_diff(parse_diff(SIMPLE), diagnostic)
    assert exc.value.code == "model_invalid_output" and diagnostic.outcome == "schema"


def multi_file():
    return SIMPLE.replace("+new", "+" + "x" * 2400) + SIMPLE.replace("a.txt", "b.txt").replace(
        "+new", "+" + "y" * 2400
    )


def test_plan_preserves_ids_and_never_splits_hunks(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    parsed = parse_diff(multi_file())
    audit, groups = plan_batches(parsed)
    assert len(groups) == 2
    assert [
        h.hunk_id for g in groups for f in g.files for h in f.hunks
    ] == audit.unanalyzed_hunk_ids
    assert tuple(f for g in groups for f in g.files) == parsed.files
    huge = parse_diff(SIMPLE.replace("+new", "+" + "x" * 5000))
    blocked, _ = plan_batches(huge)
    assert blocked.batches[0].error_code == "hunk_too_large"
    assert blocked.request_count == 0


def test_single_file_multiple_hunks_keep_original_coordinates(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    parsed = parse_diff(
        SIMPLE.replace("+new", "+" + "x" * 2400) + "@@ -50 +50 @@\n-old\n+" + "y" * 2400 + "\n"
    )
    _, groups = plan_batches(parsed)
    assert len(groups) == 2
    assert [g.files[0].hunks[0] for g in groups] == list(parsed.files[0].hunks)
    assert groups[1].files[0].hunks[0].lines[-1].new_line == 50


def test_partial_keeps_completed_batches_and_limit_without_retry(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    monkeypatch.setenv("INSPECTOR_MAX_AUDIT_REQUESTS", "1")
    calls, saved = [], []

    def complete(parsed, diagnostic):
        calls.append(parsed)
        diagnostic.outcome = "completed"
        return ModelReview(summary="Only this batch", findings=[])

    monkeypatch.setattr(analysis, "review_diff", complete)
    with audit_progress(lambda audit, result: saved.append(audit.model_dump())):
        result = analysis.analyze_parsed(parse_diff(multi_file()))
    assert len(calls) == result.audit.request_count == 1
    assert result.audit.status == "partial" and saved[0]["status"] == "analyzing"
    assert [b.status for b in result.audit.batches] == ["completed", "pending"]
    assert result.audit.batches[1].error_code == "request_limit"
    assert len(result.audit.unanalyzed_hunk_ids) == 1


def test_failed_batch_does_not_discard_later_success(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    calls = []

    def provider(parsed, diagnostic):
        calls.append(parsed)
        if len(calls) == 1:
            diagnostic.outcome = "incomplete"
            raise AnalysisError("model_incomplete", "Incomplete")
        diagnostic.outcome = "completed"
        return ModelReview(summary="Second only", findings=[])

    monkeypatch.setattr(analysis, "review_diff", provider)
    result = analysis.analyze_parsed(parse_diff(multi_file()))
    assert result.audit.status == "partial" and len(calls) == 2
    assert [b.status for b in result.audit.batches] == ["incomplete", "completed"]


def test_refs_checked_against_snapshot_and_batch_and_exact_duplicates(monkeypatch):
    body = review_body()
    body["findings"] *= 2
    monkeypatch.setattr(analysis, "review_diff", lambda p, d: ModelReview.model_validate(body))
    result = analysis.analyze_parsed(parse_diff(SIMPLE))
    assert len(result.findings) == 1
    assert result.findings[0].batch_ids == ["batch-1"]
    assert result.findings[0].reference_checks[0].diff_line == 6
    assert result.findings[0].all_references_valid


def test_compact_payload_is_lossless_for_evidence():
    text = SIMPLE.replace("+new", "+  new\t") + "\\ No newline at end of file\n"
    parsed = parse_diff(text)
    compact = json.loads(model_payload(parsed))
    for original_file, file in zip(parsed.files, compact["files"], strict=True):
        assert original_file.file_id == file["file_id"]
        for original_hunk, hunk in zip(original_file.hunks, file["hunks"], strict=True):
            assert original_hunk.hunk_id == hunk["hunk_id"]
            assert hunk["lines"] == [
                [line.kind, line.old_line, line.new_line, line.content, line.no_newline]
                for line in original_hunk.lines
            ]
    assert len(model_payload(parsed).encode()) < len(original_payload(parsed).encode())
    assert asdict(parse_diff(text)) == asdict(parsed)


def test_persisted_partial_results_and_historical_terminal_unchanged(
    api, authorized_root, mock_meta, monkeypatch
):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    monkeypatch.setenv("INSPECTOR_MAX_AUDIT_REQUESTS", "1")
    install, calls, _ = mock_meta
    install(envelope({"summary": "Batch complete", "findings": []}))
    snapshot = register(api, authorized_root, multi_file())
    url = f"/api/reviews/{snapshot['review_id']}"
    result = api.post(url + "/analyze", headers=HEADERS, json={}).json()
    assert result["status"] == "error" and result["error"]["code"] == "audit_partial"
    assert result["analysis"]["audit"]["status"] == result["audit"]["status"] == "partial"
    assert api.post(url + "/analyze", headers=HEADERS, json={}).json() == result
    assert api.get(url).json() == result and len(calls) == 1


def test_safety_blocks_before_any_provider_call(api, authorized_root, mock_meta):
    _, calls, _ = mock_meta
    response = api.post(
        "/api/reviews",
        headers=HEADERS,
        json={
            "repository": "project",
            "repository_root": str(authorized_root),
            "scope": "unstaged",
            "diff": SIMPLE.replace("a.txt", ".env"),
        },
    )
    assert response.status_code == 403 and not calls


def test_invalid_configuration_never_calls_provider(monkeypatch):
    monkeypatch.setenv("INSPECTOR_MAX_AUDIT_REQUESTS", "999")
    with pytest.raises(AnalysisError, match="configuration"):
        analysis.analyze_parsed(parse_diff(SIMPLE))


def test_migration_is_additive_and_does_not_change_historical_rows(tmp_path):
    from app.review_store import SCHEMA

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT INTO reviews(review_id,repository,repository_root,origin,scope,created_at,"
            "diff,diff_sha256,parsed_json,status,error_json) "
            "VALUES ('old','demo','root','mcp','unstaged','old',"
            "'original','hash','{}','error','{}')"
        )
        before = c.execute("SELECT * FROM reviews").fetchone()
    ReviewRepository(path, "http://127.0.0.1:5173")
    with sqlite3.connect(path) as c:
        after = c.execute("SELECT * FROM reviews").fetchone()
    assert after[: len(before)] == before and after[-1] is None


def test_crash_preserves_completed_findings_and_does_not_resume(
    api, authorized_root, mock_meta, monkeypatch
):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    _, calls, _ = mock_meta
    original = analysis.review_diff
    count = 0

    def crash(parsed, diagnostic):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("Simulated process failure; never expose this")
        return original(parsed, diagnostic)

    monkeypatch.setattr(analysis, "review_diff", crash)
    snapshot = register(api, authorized_root, multi_file())
    url = f"/api/reviews/{snapshot['review_id']}"
    result = api.post(url + "/analyze", headers=HEADERS, json={}).json()
    assert result["status"] == "error" and result["audit"]["status"] == "partial"
    assert result["analysis"] is not None
    assert result["audit"]["request_count"] == 2
    assert result["audit"]["batches"][0]["status"] == "completed"
    assert result["audit"]["batches"][1]["status"] == "pending"
    assert "Simulated" not in json.dumps(result)
    assert api.post(url + "/analyze", headers=HEADERS, json={}).json() == result
    assert len(calls) == 1


def test_oversize_hunk_never_calls_model(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")

    def forbidden(*args):
        raise AssertionError("Oversized hunk must not be sent")

    monkeypatch.setattr(analysis, "review_diff", forbidden)
    with pytest.raises(AnalysisError) as exc:
        analysis.analyze_parsed(parse_diff(SIMPLE.replace("+new", "+" + "x" * 5000)))
    assert exc.value.audit.request_count == 0
    assert exc.value.audit.batches[0].error_code == "hunk_too_large"


def test_cross_batch_reference_is_visible_but_invalid(monkeypatch):
    monkeypatch.setenv("INSPECTOR_BATCH_BYTES", "4096")
    parsed = parse_diff(multi_file())
    body = review_body()
    file = parsed.files[1]
    body["findings"][0]["references"][0].update(
        file_id=file.file_id,
        hunk_id=file.hunks[0].hunk_id,
        path=file.new_path,
        quote="y" * 2400,
    )
    monkeypatch.setattr(analysis, "review_diff", lambda p, d: ModelReview.model_validate(body))
    result = analysis.analyze_parsed(parsed)
    assert not result.findings[0].all_references_valid
    assert result.findings[0].reference_checks[0].reason == "hunk_not_found"
    assert result.findings[1].all_references_valid
    assert result.findings[1].batch_ids == ["batch-2"]
