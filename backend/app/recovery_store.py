"""Append-only recovery results. Original reviews and finding indexes never change."""

import json
from uuid import uuid4

from app.analysis_models import AnalysisResponse
from app.inspection_models import RecoverableError
from app.provider_models import ProviderDiagnostic
from app.recovery_models import RecoveryAttempt, RecoveryResult, RecoveryView
from app.review_models import ReviewError
from app.services.model_client import MODEL, AnalysisError
from app.services.recovery_recipes import reconstruct_batches, recovery_limits

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_recovery_runs (
 request_id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(review_id),
 selection_json TEXT NOT NULL, expected_version INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','completed','interrupted')),
 effective_status TEXT NOT NULL, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_recovery
 ON review_recovery_runs(review_id) WHERE status='active';
CREATE INDEX IF NOT EXISTS recovery_review_idx ON review_recovery_runs(review_id,created_at);
CREATE TABLE IF NOT EXISTS review_batch_attempts (
 attempt_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES review_recovery_runs(request_id),
 review_id TEXT NOT NULL REFERENCES reviews(review_id), batch_id TEXT NOT NULL,
 number INTEGER NOT NULL CHECK(number>=2),
 status TEXT NOT NULL CHECK(status IN (
 'pending','running','completed','failed','incomplete','interrupted')),
 created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, output_budget INTEGER NOT NULL,
 diagnostics_json TEXT, result_json TEXT, error_code TEXT,
 UNIQUE(review_id,batch_id,number), UNIQUE(request_id,batch_id)
);
CREATE INDEX IF NOT EXISTS attempts_review_idx ON review_batch_attempts(review_id,created_at);
CREATE TRIGGER IF NOT EXISTS immutable_recovery_run
 BEFORE UPDATE ON review_recovery_runs WHEN OLD.status!='active'
 BEGIN SELECT RAISE(ABORT, 'terminal recovery'); END;
CREATE TRIGGER IF NOT EXISTS immutable_attempt
 BEFORE UPDATE ON review_batch_attempts WHEN OLD.status NOT IN ('pending','running')
 BEGIN SELECT RAISE(ABORT, 'terminal attempt'); END;
CREATE TRIGGER IF NOT EXISTS immutable_attempt_identity
 BEFORE UPDATE OF attempt_id,request_id,review_id,batch_id,number,created_at,output_budget
 ON review_batch_attempts BEGIN SELECT RAISE(ABORT, 'immutable attempt identity'); END;
CREATE TRIGGER IF NOT EXISTS immutable_run_identity
 BEFORE UPDATE OF request_id,review_id,selection_json,expected_version,created_at
 ON review_recovery_runs BEGIN SELECT RAISE(ABORT, 'immutable recovery identity'); END;
CREATE TRIGGER IF NOT EXISTS no_attempt_delete BEFORE DELETE ON review_batch_attempts
 BEGIN SELECT RAISE(ABORT, 'immutable attempt'); END;
CREATE TRIGGER IF NOT EXISTS no_recovery_delete BEFORE DELETE ON review_recovery_runs
 BEGIN SELECT RAISE(ABORT, 'immutable recovery'); END;
"""

EFFECTIVE_STATUS = (
    "COALESCE((SELECT effective_status FROM review_recovery_runs rr "
    "WHERE rr.review_id=reviews.review_id ORDER BY rr.rowid DESC LIMIT 1),reviews.status)"
)


class RecoveryStore:
    def __init__(self, repository):
        self.repository = repository

    def rows(self, review_id, connection=None):
        if connection is None:
            with self.repository.connection() as c:
                c.execute("BEGIN")
                return self.rows(review_id, c)
        attempts = connection.execute(
            "SELECT * FROM review_batch_attempts WHERE review_id=? ORDER BY rowid", (review_id,)
        ).fetchall()
        runs = connection.execute(
            "SELECT * FROM review_recovery_runs WHERE review_id=? ORDER BY rowid", (review_id,)
        ).fetchall()
        return attempts, runs

    def decorate(self, snapshot, rows=None, ignore_active=False):
        attempts, runs = rows if rows is not None else self.rows(snapshot.review_id)
        view = RecoveryView(
            original_status=snapshot.status,
            original_finished_at=snapshot.finished_at,
            original_audit=snapshot.audit,
        )
        view.version = len(attempts)
        view.attempts = [
            RecoveryAttempt(
                **{k: row[k] for k in RecoveryAttempt.model_fields if k != "diagnostics"},
                diagnostics=json.loads(row["diagnostics_json"])
                if row["diagnostics_json"]
                else None,
            )
            for row in attempts
        ]
        active = next((r for r in runs if r["status"] == "active"), None)
        view.active_request_id = active["request_id"] if active and not ignore_active else None
        try:
            limits = recovery_limits()
            view.max_calls_per_action = limits["per_action"]
            view.max_per_batch = limits["per_batch"]
            view.max_per_review = limits["per_review"]
            view.remaining_review = max(0, limits["per_review"] - len(attempts))
            view.output_budget = limits["output_budget"]
            reconstruct_batches(snapshot)
            view.supported = snapshot.status in ("completed", "error")
            if not view.supported:
                view.blocked_reason = "recovery_not_terminal"
        except (AnalysisError, ReviewError, ValueError) as exc:
            limits = None
            view.blocked_reason = getattr(exc, "code", "recovery_unavailable")
            if view.blocked_reason not in ("invalid_output_budget", "invalid_audit_config"):
                view.blocked_reason = "recovery_unavailable"

        # Read projection only; originals remain byte-for-byte in reviews.
        audit = snapshot.audit.model_copy(deep=True) if snapshot.audit else None
        analysis = snapshot.analysis.model_copy(deep=True) if snapshot.analysis else None
        if attempts and audit:
            batches = {b.batch_id: b for b in audit.batches}
            if analysis:
                for finding in analysis.findings:
                    finding.attempt_ids = ["initial:" + b for b in finding.batch_ids]
            for row in attempts:
                batch = batches.get(row["batch_id"])
                if batch is None:
                    continue
                if row["status"] == "completed" and row["result_json"]:
                    result = RecoveryResult.model_validate_json(row["result_json"])
                    if analysis is None:
                        analysis = AnalysisResponse(
                            model=MODEL, summary="", findings=[], parsed_diff=snapshot.parsed_diff
                        )
                    analysis.summary += (
                        f"\n\n[{batch.batch_id} / attempt {row['number']}] {result.summary}"
                    )
                    analysis.findings.extend(result.findings)
                    batch.status, batch.error_code = "completed", None
                elif batch.status != "completed":
                    batch.status = (
                        "incomplete"
                        if row["status"] == "incomplete"
                        else "failed"
                        if row["status"] in ("failed", "interrupted")
                        else "pending"
                    )
                    batch.error_code = row["error_code"]
                if row["diagnostics_json"]:
                    batch.diagnostics = ProviderDiagnostic.model_validate_json(
                        row["diagnostics_json"]
                    )
            # Revalidate assignment types (diagnostic rows are safe projections).
            audit = type(audit).model_validate(audit.model_dump())
            audit.completed_hunk_ids = [
                h for b in audit.batches if b.status == "completed" for h in b.hunk_ids
            ]
            audit.unanalyzed_hunk_ids = [
                h for b in audit.batches if b.status != "completed" for h in b.hunk_ids
            ]
            audit.request_count += sum(row["started_at"] is not None for row in attempts)
            audit.max_requests += limits["per_review"] if limits else len(attempts)
            audit.status = (
                "analyzing"
                if view.active_request_id
                else "completed"
                if not audit.unanalyzed_hunk_ids
                else "partial"
                if audit.completed_hunk_ids
                else "incomplete"
            )
            snapshot.status = (
                "analyzing"
                if view.active_request_id
                else "completed"
                if audit.status == "completed"
                else "error"
            )
            snapshot.error = (
                None
                if snapshot.status != "error"
                else RecoverableError(
                    code="audit_partial" if audit.status == "partial" else "audit_incomplete",
                    message="See recovery coverage.",
                )
            )
            snapshot.finished_at = runs[-1]["finished_at"]
            snapshot.audit = audit
            if analysis:
                analysis.audit = audit
                snapshot.analysis = analysis

        if view.supported and audit and limits:
            for batch in audit.batches:
                count = sum(a["batch_id"] == batch.batch_id for a in attempts)
                reason = (
                    "recovery_busy"
                    if view.active_request_id
                    else "recovery_completed"
                    if batch.status == "completed"
                    else "recovery_pending"
                    if batch.status == "pending"
                    else "hunk_too_large"
                    if batch.payload_bytes > limits["batch_bytes"]
                    else "recovery_limit"
                    if count >= limits["per_batch"] or not view.remaining_review
                    else None
                )
                if reason:
                    view.batch_blockers[batch.batch_id] = reason
                else:
                    view.eligible_batch_ids.append(batch.batch_id)
        snapshot.recovery = view
        return snapshot

    def admit(self, original, data):
        from app.review_store import now

        request_id = str(data.request_id)
        with self.repository.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute(
                "SELECT * FROM review_recovery_runs WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                budgets = {
                    r[0]
                    for r in c.execute(
                        "SELECT output_budget FROM review_batch_attempts WHERE request_id=?",
                        (request_id,),
                    )
                }
                if (
                    budgets != {data.expected_output_budget}
                    or existing["review_id"] != original.review_id
                    or json.loads(existing["selection_json"]) != data.batch_ids
                    or existing["expected_version"] != data.expected_version
                ):
                    raise ReviewError("recovery_conflict", "Recovery request ID already used.", 409)
                return False
            decorated = self.decorate(
                original.model_copy(deep=True), self.rows(original.review_id, c)
            )
            view = decorated.recovery
            if not view.supported:
                raise ReviewError(
                    "recovery_unavailable", "Stored review cannot be recovered safely.", 409
                )
            if view.active_request_id:
                raise ReviewError("recovery_busy", "Another recovery is active.", 409)
            if (
                data.expected_version != view.version
                or data.expected_output_budget != view.output_budget
            ):
                raise ReviewError(
                    "recovery_conflict", "Refresh recovery state before confirming.", 409
                )
            ids = data.batch_ids
            if len(set(ids)) != len(ids) or not set(ids) <= set(view.eligible_batch_ids):
                raise ReviewError("recovery_not_eligible", "Select only eligible batches.", 409)
            if len(ids) > min(view.max_calls_per_action, view.remaining_review):
                raise ReviewError("recovery_limit", "Recovery request limit reached.", 409)
            timestamp = now()
            c.execute(
                "INSERT INTO review_recovery_runs VALUES (?,?,?,?, "
                "'active','analyzing',NULL,?,NULL)",
                (request_id, original.review_id, json.dumps(ids), data.expected_version, timestamp),
            )
            attempts, _ = self.rows(original.review_id, c)
            for batch_id in ids:
                number = 2 + sum(a["batch_id"] == batch_id for a in attempts)
                c.execute(
                    "INSERT INTO "
                    "review_batch_attempts(attempt_id,request_id,review_id,batch_id,"
                    "number,status,created_at,output_budget) VALUES (?,?,?,?,?,'pending',?,?)",
                    (
                        str(uuid4()),
                        request_id,
                        original.review_id,
                        batch_id,
                        number,
                        timestamp,
                        view.output_budget,
                    ),
                )
        return True

    def start(self, attempt_id):
        from app.review_store import now

        with self.repository.connection() as c:
            return (
                c.execute(
                    "UPDATE review_batch_attempts SET status='running',started_at=? "
                    "WHERE attempt_id=? AND status='pending' AND EXISTS(SELECT 1 FROM "
                    "review_recovery_runs r WHERE "
                    "r.request_id=review_batch_attempts.request_id AND r.status='active')",
                    (now(), attempt_id),
                ).rowcount
                == 1
            )

    def finish_attempt(self, attempt_id, status, diagnostic, result=None, error_code=None):
        from app.review_store import now

        with self.repository.connection() as c:
            c.execute(
                "UPDATE review_batch_attempts SET "
                "status=?,finished_at=?,diagnostics_json=?,result_json=?,error_code=? "
                "WHERE attempt_id=? AND status='running'",
                (
                    status,
                    now(),
                    diagnostic.model_dump_json(),
                    result.model_dump_json() if result else None,
                    error_code,
                    attempt_id,
                ),
            )

    def close(self, review_id, request_id, interrupted=False):
        from app.review_store import now

        with self.repository.connection() as c:
            c.execute(
                "UPDATE review_batch_attempts SET "
                "status='interrupted',finished_at=?,error_code=? "
                "WHERE request_id=? AND status IN ('pending','running')",
                (now(), "recovery_interrupted" if interrupted else "recovery_stopped", request_id),
            )
        original = self.repository.get(review_id, include_recovery=False)
        effective = self.decorate(original, ignore_active=True)
        with self.repository.connection() as c:
            c.execute(
                "UPDATE review_recovery_runs SET "
                "status=?,effective_status=?,error_code=?,finished_at=? WHERE "
                "request_id=? AND status='active'",
                (
                    "interrupted" if interrupted else "completed",
                    effective.status,
                    effective.error.code if effective.error else None,
                    now(),
                    request_id,
                ),
            )

    def recover_interrupted(self):
        with self.repository.connection() as c:
            rows = c.execute(
                "SELECT review_id,request_id FROM review_recovery_runs WHERE status='active'"
            ).fetchall()
        for row in rows:
            self.close(row["review_id"], row["request_id"], interrupted=True)
