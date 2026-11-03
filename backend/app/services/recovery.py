"""One explicitly confirmed recovery action. Never reads Git or runs repository code."""

import sys

from app.provider_models import ProviderDiagnostic
from app.recovery_models import RecoveryResult
from app.recovery_store import RecoveryStore
from app.services.model_client import AnalysisError, review_diff
from app.services.reference_validator import check_findings


def execute_recovery(repository, original, data, parsed, groups, preflight):
    store = RecoveryStore(repository)
    if not store.admit(original, data):
        return repository.get(original.review_id)
    request_id = str(data.request_id)
    try:
        attempts, _ = store.rows(original.review_id)
        for row in (r for r in attempts if r["request_id"] == request_id):
            if not store.start(row["attempt_id"]):
                continue
            diagnostic = ProviderDiagnostic(max_output_tokens=row["output_budget"])
            try:
                preflight()
                review = review_diff(
                    groups[row["batch_id"]], diagnostic, max_output_tokens=row["output_budget"]
                )
                findings = check_findings(parsed, review)
                allowed = {h.hunk_id for f in groups[row["batch_id"]].files for h in f.hunks}
                for finding in findings:
                    for check in finding.reference_checks:
                        if check.reference.hunk_id not in allowed:
                            check.status, check.reason, check.diff_line = (
                                "invalid",
                                "hunk_not_found",
                                None,
                            )
                    finding.all_references_valid = all(
                        c.status == "valid" for c in finding.reference_checks
                    )
                    finding.batch_ids = [row["batch_id"]]
                    finding.attempt_ids = [row["attempt_id"]]
                unique = {f.model_dump_json(): f for f in findings}
                store.finish_attempt(
                    row["attempt_id"],
                    "completed",
                    diagnostic,
                    RecoveryResult(summary=review.summary, findings=list(unique.values())),
                )
            except AnalysisError as exc:
                store.finish_attempt(
                    row["attempt_id"],
                    "incomplete" if diagnostic.outcome in ("budget", "incomplete") else "failed",
                    diagnostic,
                    error_code=exc.code,
                )
                if exc.code in (
                    "model_auth_error",
                    "model_rate_limited",
                    "model_not_configured",
                    "invalid_output_budget",
                ):
                    break
            except Exception as exc:
                code = getattr(exc, "code", "recovery_failed")
                if code not in (
                    "unauthorized_repository",
                    "sensitive_path",
                    "possible_secret",
                    "unsafe_diff_path",
                    "unsupported_change",
                ):
                    code = "recovery_failed"
                store.finish_attempt(row["attempt_id"], "failed", diagnostic, error_code=code)
                break
    finally:
        store.close(original.review_id, request_id, interrupted=sys.exc_info()[0] is not None)
    return repository.get(original.review_id)
