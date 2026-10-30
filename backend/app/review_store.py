"""SQLite snapshots and analysis transitions; no Git, provider or parser execution."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.analysis_models import AnalysisResponse
from app.feedback_models import FeedbackWrite, HumanFeedback, ReviewFeedback
from app.inspection_models import RecoverableError
from app.models import ParseResponse
from app.review_models import ReviewCreate, ReviewDetail, ReviewError, ReviewPage, ReviewSummary

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    repository TEXT NOT NULL, repository_root TEXT NOT NULL,
    origin TEXT NOT NULL CHECK(origin = 'mcp'), scope TEXT NOT NULL,
    created_at TEXT NOT NULL, finished_at TEXT,
    diff TEXT NOT NULL, diff_sha256 TEXT NOT NULL, parsed_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','analyzing','completed','error')),
    analysis_json TEXT, error_json TEXT
);
CREATE TRIGGER IF NOT EXISTS immutable_snapshot
BEFORE UPDATE OF review_id, repository, repository_root, origin, scope,
                 created_at, diff, diff_sha256, parsed_json ON reviews
BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS terminal_result
BEFORE UPDATE ON reviews WHEN OLD.status IN ('completed','error')
BEGIN SELECT RAISE(ABORT, 'terminal review'); END;
CREATE TABLE IF NOT EXISTS review_links (
    child_id TEXT PRIMARY KEY REFERENCES reviews(review_id),
    parent_id TEXT NOT NULL REFERENCES reviews(review_id),
    CHECK(child_id != parent_id)
);
CREATE TRIGGER IF NOT EXISTS immutable_link_update BEFORE UPDATE ON review_links
BEGIN SELECT RAISE(ABORT, 'immutable link'); END;
CREATE TRIGGER IF NOT EXISTS immutable_link_delete BEFORE DELETE ON review_links
BEGIN SELECT RAISE(ABORT, 'immutable link'); END;
CREATE TABLE IF NOT EXISTS human_decisions (
    review_id TEXT NOT NULL REFERENCES reviews(review_id),
    finding_index INTEGER NOT NULL CHECK(finding_index >= 0),
    decision TEXT NOT NULL CHECK(decision IN ('request_changes','accept_risk','dismiss')),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(review_id, finding_index)
);
CREATE TABLE IF NOT EXISTS human_comments (
    review_id TEXT NOT NULL, finding_index INTEGER NOT NULL,
    comment TEXT NOT NULL CHECK(length(comment) <= 4000),
    FOREIGN KEY(review_id, finding_index) REFERENCES human_decisions(review_id, finding_index),
    PRIMARY KEY(review_id, finding_index)
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewRepository:
    def __init__(self, path: Path, web_base: str):
        self.path = path
        self.web_base = web_base
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.row_factory = sqlite3.Row
            with connection:
                yield connection
        except (sqlite3.Error, OSError) as exc:
            raise ReviewError(
                "storage_unavailable", "No se pudo acceder al almacén local."
            ) from exc
        finally:
            if connection is not None:
                connection.close()

    def _summary(self, row: sqlite3.Row) -> dict:
        return {
            key: row[key]
            for key in (
                "review_id",
                "repository",
                "repository_root",
                "origin",
                "scope",
                "created_at",
                "finished_at",
                "status",
                "diff_sha256",
            )
        } | {
            "review_url": f"{self.web_base}/reviews/{row['review_id']}",
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
        }

    def get(self, review_id: str) -> ReviewDetail:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
            parent = connection.execute(
                "SELECT parent_id FROM review_links WHERE child_id=?", (review_id,)
            ).fetchone()
            children = connection.execute(
                "SELECT child_id FROM review_links WHERE parent_id=? ORDER BY child_id",
                (review_id,),
            ).fetchall()
            feedback = connection.execute(
                "SELECT d.finding_index,d.decision,d.updated_at,COALESCE(c.comment,'') AS comment "
                "FROM human_decisions d LEFT JOIN human_comments c "
                "USING(review_id,finding_index) WHERE d.review_id=? ORDER BY d.finding_index",
                (review_id,),
            ).fetchall()
        if row is None:
            raise ReviewError("review_not_found", "No se encontró la revisión.", 404)
        return ReviewDetail(
            **self._summary(row),
            diff=row["diff"],
            parsed_diff=ParseResponse.model_validate_json(row["parsed_json"]),
            analysis=AnalysisResponse.model_validate_json(row["analysis_json"])
            if row["analysis_json"]
            else None,
            parent_review_id=parent[0] if parent else None,
            child_review_ids=[child[0] for child in children],
            feedback=[HumanFeedback(**dict(item)) for item in feedback],
        )

    def list(self, limit: int, offset: int) -> ReviewPage:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT review_id,repository,repository_root,origin,scope,created_at,finished_at,"
                "status,diff_sha256,error_json FROM reviews "
                "ORDER BY created_at DESC, review_id DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        return ReviewPage(items=[ReviewSummary(**self._summary(row)) for row in rows], total=total)

    def create(self, request: ReviewCreate, parsed: ParseResponse) -> ReviewDetail:
        identifier = str(request.review_id)
        parent_id = str(request.parent_review_id) if request.parent_review_id else None
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existed = connection.execute(
                "SELECT 1 FROM reviews WHERE review_id=?", (identifier,)
            ).fetchone()
            link = connection.execute(
                "SELECT parent_id FROM review_links WHERE child_id=?", (identifier,)
            ).fetchone()
            if existed and (link[0] if link else None) != parent_id:
                raise ReviewError("review_conflict", "Review ancestry cannot be changed.", 409)
            if parent_id is not None:
                parent = connection.execute(
                    "SELECT repository,repository_root FROM reviews WHERE review_id=?", (parent_id,)
                ).fetchone()
                if parent is None:
                    raise ReviewError(
                        "parent_review_not_found", "Parent review does not exist.", 404
                    )
                if parent_id == identifier or tuple(parent) != (
                    request.repository,
                    request.repository_root,
                ):
                    raise ReviewError(
                        "invalid_review_relationship",
                        "Reviews must belong to the same repository.",
                        409,
                    )
            connection.execute(
                "INSERT INTO reviews (review_id,repository,repository_root,origin,scope,"
                "created_at,diff,diff_sha256,parsed_json,status) "
                "VALUES (?,?,?,'mcp',?,?,?,?,?,'pending') ON CONFLICT(review_id) DO NOTHING",
                (
                    identifier,
                    request.repository,
                    request.repository_root,
                    request.scope,
                    now(),
                    request.diff,
                    hashlib.sha256(request.diff.encode("utf-8")).hexdigest(),
                    parsed.model_dump_json(),
                ),
            )
            existing = connection.execute(
                "SELECT * FROM reviews WHERE review_id = ?", (identifier,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["diff"],
                    existing["repository"],
                    existing["repository_root"],
                    existing["scope"],
                ) != (request.diff, request.repository, request.repository_root, request.scope):
                    raise ReviewError(
                        "review_conflict", "El ID ya identifica otra instantánea.", 409
                    )
            if parent_id is not None and not existed:
                connection.execute(
                    "INSERT INTO review_links(child_id,parent_id) VALUES (?,?)",
                    (identifier, parent_id),
                )
        return self.get(identifier)

    def save_feedback(
        self, review_id: str, finding_index: int, data: FeedbackWrite
    ) -> HumanFeedback:
        snapshot = self.get(review_id)
        if snapshot.status != "completed" or snapshot.analysis is None:
            raise ReviewError("feedback_not_ready", "Analysis has no reviewable findings.", 409)
        if not 0 <= finding_index < len(snapshot.analysis.findings):
            raise ReviewError("finding_not_found", "Finding does not exist.", 404)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp = now()
            connection.execute(
                "INSERT INTO human_decisions VALUES (?,?,?,?) "
                "ON CONFLICT(review_id,finding_index) DO UPDATE SET "
                "decision=excluded.decision,updated_at=excluded.updated_at",
                (review_id, finding_index, data.decision, timestamp),
            )
            connection.execute(
                "INSERT INTO human_comments VALUES (?,?,?) "
                "ON CONFLICT(review_id,finding_index) DO UPDATE SET comment=excluded.comment",
                (review_id, finding_index, data.comment),
            )
        return HumanFeedback(
            finding_index=finding_index,
            decision=data.decision,
            comment=data.comment,
            updated_at=timestamp,
        )

    def feedback(self, review_id: str) -> ReviewFeedback:
        snapshot = self.get(review_id)
        decisions = {item.finding_index: item for item in snapshot.feedback}
        items = [
            {
                **decisions.get(index, HumanFeedback(finding_index=index)).model_dump(),
                "finding": finding,
            }
            for index, finding in enumerate(snapshot.analysis.findings if snapshot.analysis else [])
        ]
        return ReviewFeedback(
            review_id=review_id,
            repository=snapshot.repository,
            repository_root=snapshot.repository_root,
            review_url=snapshot.review_url,
            analysis_status=snapshot.status,
            parent_review_id=snapshot.parent_review_id,
            child_review_ids=snapshot.child_review_ids,
            items=items,
            pending_count=sum(item["decision"] is None for item in items),
        )

    def claim(self, review_id: str) -> bool:
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE reviews SET status='analyzing' WHERE review_id=? AND status='pending'",
                (review_id,),
            ).rowcount
        return changed == 1

    def finish(
        self, review_id: str, analysis: AnalysisResponse | None, error: RecoverableError | None
    ) -> None:
        if (analysis is None) == (error is None):
            raise ValueError("Exactly one analysis or error must be recorded.")
        with self.connection() as connection:
            connection.execute(
                "UPDATE reviews SET status=?,finished_at=?,analysis_json=?,error_json=? "
                "WHERE review_id=? AND status='analyzing'",
                (
                    "completed" if analysis is not None else "error",
                    now(),
                    analysis.model_dump_json() if analysis is not None else None,
                    error.model_dump_json() if error is not None else None,
                    review_id,
                ),
            )

    def recover_interrupted(self) -> None:
        error = RecoverableError(
            code="analysis_interrupted",
            message=(
                "El servicio se interrumpió durante el análisis. La instantánea se conserva; "
                "no se reintentó la llamada al modelo."
            ),
        )
        with self.connection() as connection:
            connection.execute(
                "UPDATE reviews SET status='error',finished_at=?,error_json=? "
                "WHERE status='analyzing'",
                (now(), error.model_dump_json()),
            )
