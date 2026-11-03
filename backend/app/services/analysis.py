"""Bounded analysis against one snapshot, with independently checked references."""

from dataclasses import asdict

from app.analysis_models import AnalysisResponse
from app.models import ParseResponse
from app.provider_models import ProviderDiagnostic
from app.services.audit_batches import plan_batches, report_progress
from app.services.diff_parser import ParsedDiff
from app.services.model_client import MODEL, AnalysisError, review_diff
from app.services.output_budget import output_budget
from app.services.reference_validator import check_findings


def analyze_parsed(parsed: ParsedDiff) -> AnalysisResponse:
    budget = output_budget()
    audit, groups = plan_batches(parsed)
    if not groups:
        raise AnalysisError("no_text_changes", "El diff no contiene hunks de texto.", 422)
    audit.status = "analyzing"
    findings = []
    summaries = []
    fingerprints = {}
    first_error = None

    def result():
        return AnalysisResponse(
            model=MODEL,
            summary="\n\n".join(summaries),
            findings=findings,
            parsed_diff=ParseResponse.model_validate(asdict(parsed)),
            audit=audit,
        )

    report_progress(audit, None)
    stop = False
    for batch, group in zip(audit.batches, groups, strict=True):
        if batch.status == "failed":
            continue
        if stop or audit.request_count >= audit.max_requests:
            batch.error_code = "audit_stopped" if stop else "request_limit"
            continue
        diagnostic = ProviderDiagnostic(max_output_tokens=budget)
        batch.diagnostics = diagnostic
        # Persist intent before the call. A crash leaves this batch pending, never retried.
        audit.request_count += 1
        report_progress(audit, result() if summaries else None)
        try:
            review = review_diff(group, diagnostic)
        except AnalysisError as exc:
            batch.error_code = exc.code
            batch.status = (
                "incomplete" if diagnostic.outcome in ("budget", "incomplete") else "failed"
            )
            first_error = first_error or exc
            stop = exc.code in ("model_not_configured", "model_auth_error", "model_rate_limited")
        else:
            batch.status = "completed"
            summaries.append(f"[{batch.batch_id}] {review.summary}")
            # Validate against the original snapshot, then restrict provenance to this batch.
            for checked in check_findings(parsed, review):
                for refcheck in checked.reference_checks:
                    if refcheck.reference.hunk_id not in batch.hunk_ids:
                        refcheck.status, refcheck.reason, refcheck.diff_line = (
                            "invalid",
                            "hunk_not_found",
                            None,
                        )
                checked.all_references_valid = all(
                    c.status == "valid" for c in checked.reference_checks
                )
                fingerprint = checked.model_dump_json(exclude={"batch_ids"})
                if fingerprint in fingerprints:
                    origins = findings[fingerprints[fingerprint]].batch_ids
                    if batch.batch_id not in origins:
                        origins.append(batch.batch_id)
                else:
                    checked.batch_ids = [batch.batch_id]
                    fingerprints[fingerprint] = len(findings)
                    findings.append(checked)
            audit.completed_hunk_ids.extend(batch.hunk_ids)
            audit.unanalyzed_hunk_ids = [
                h for h in audit.unanalyzed_hunk_ids if h not in batch.hunk_ids
            ]
        if diagnostic.outcome == "preflight":
            audit.request_count -= 1
        report_progress(audit, result() if summaries else None)
    complete = all(b.status == "completed" for b in audit.batches)
    audit.status = "completed" if complete else "partial" if summaries else "incomplete"
    report_progress(audit, result() if summaries else None)
    if not summaries:
        error = first_error or AnalysisError("audit_incomplete", "No batches completed.")
        error.audit = audit
        raise error
    return result()
