from dataclasses import asdict
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi import Path as ApiPath
from pydantic import UUID4

from app.audit_models import AgentSource
from app.feedback_models import FeedbackWrite, HumanFeedback, ReviewFeedback
from app.inspection_models import InspectionError, RecoverableError
from app.local_settings import database_path, web_repositories, web_url
from app.models import ParseResponse
from app.recovery_models import RecoveryRequest
from app.review_models import (
    ReviewComparison,
    ReviewCreate,
    ReviewDetail,
    ReviewError,
    ReviewPage,
    ReviewTimeline,
)
from app.review_store import ReviewRepository
from app.services.analysis import analyze_parsed
from app.services.audit_batches import audit_progress
from app.services.diff_parser import DiffParseError, parse_diff
from app.services.egress_guard import check_egress
from app.services.model_client import AnalysisError
from app.services.recovery import execute_recovery
from app.services.recovery_recipes import reconstruct_batches

router = APIRouter(prefix="/api/reviews")


def get_review_repository() -> ReviewRepository:
    return ReviewRepository(database_path(), web_url())


def authorized_root(repository: str, expected_root: str):
    try:
        authorized = web_repositories().get(repository)
    except (ValueError, OSError) as exc:
        raise ReviewError(
            "repository_configuration_error",
            "Revisa los repositorios autorizados del servicio web.",
        ) from exc
    if authorized is None or str(authorized.root) != expected_root:
        raise InspectionError(
            "unauthorized_repository", "Repositorio no autorizado por la web.", blocked=True
        )
    return authorized.root


@router.post("", response_model=ReviewDetail, status_code=201)
def register_review(request: ReviewCreate) -> ReviewDetail:
    root = authorized_root(request.repository, request.repository_root)
    parsed = parse_diff(request.diff)
    check_egress(root, request.diff, parsed)
    if request.capture_coverage:
        coverage = request.capture_coverage
        added = {file.new_path for file in parsed.files if file.change_type == "added"}
        if (
            not set(coverage.included_untracked) <= added
            or coverage.untracked_seen is not None
            and len(coverage.included_untracked) + sum(coverage.exclusions.values())
            != coverage.untracked_seen
            or not coverage.include_untracked
            and (
                coverage.untracked_seen is not None
                or coverage.included_untracked
                or coverage.exclusions
            )
        ):
            raise ReviewError("invalid_coverage", "Inconsistent capture metadata.", 422)
    return get_review_repository().create(request, ParseResponse.model_validate(asdict(parsed)))


@router.get("", response_model=ReviewPage)
def list_reviews(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=36, pattern=r"^[0-9a-f-]*$")] = None,
    repository: Annotated[str | None, Query(max_length=64, pattern=r"^[A-Za-z0-9_-]*$")] = None,
    status: Literal["pending", "analyzing", "completed", "error"] | None = None,
    severity: Literal["low", "medium", "high", "critical"] | None = None,
    agent_source: AgentSource | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ReviewPage:
    if date_from and date_to and date_from > date_to or date_to == date.max:
        raise ReviewError("invalid_date_range", "Invalid date range.", 422)
    return get_review_repository().list(
        limit,
        offset,
        q=q,
        repository=repository,
        status=status,
        severity=severity,
        agent_source=agent_source,
        date_from=date_from.isoformat() if date_from else None,
        date_to=(date_to + timedelta(days=1)).isoformat() if date_to else None,
    )


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(review_id: UUID4) -> ReviewDetail:
    return get_review_repository().get(str(review_id))


@router.get("/{review_id}/timeline", response_model=ReviewTimeline)
def get_timeline(review_id: UUID4) -> ReviewTimeline:
    timeline = get_review_repository().timeline(str(review_id))
    authorized_root(timeline.repository, timeline.repository_root)
    return timeline


@router.get("/{review_id}/compare/{other_id}", response_model=ReviewComparison)
def compare_reviews(review_id: UUID4, other_id: UUID4) -> ReviewComparison:
    result = get_review_repository().compare(str(review_id), str(other_id))
    authorized_root(result.parent.repository, result.parent.repository_root)
    return result


@router.get("/{review_id}/feedback", response_model=ReviewFeedback)
def get_feedback(review_id: UUID4) -> ReviewFeedback:
    store = get_review_repository()
    snapshot = store.get(str(review_id))
    authorized_root(snapshot.repository, snapshot.repository_root)
    return store.feedback(str(review_id))


@router.put("/{review_id}/feedback/{finding_index}", response_model=HumanFeedback)
def write_feedback(
    review_id: UUID4,
    finding_index: Annotated[int, ApiPath(ge=0)],
    data: FeedbackWrite,
    request: Request,
) -> HumanFeedback:
    # Browser-origin gate, not authentication: MCP exposes no matching write capability.
    if request.headers.get("origin") != web_url():
        raise ReviewError(
            "human_feedback_origin_required", "Use the local web interface for feedback.", 403
        )
    store = get_review_repository()
    snapshot = store.get(str(review_id))
    authorized_root(snapshot.repository, snapshot.repository_root)
    return store.save_feedback(str(review_id), finding_index, data)


@router.post("/{review_id}/analyze", response_model=ReviewDetail)
def analyze_review(review_id: UUID4) -> ReviewDetail:
    repository = get_review_repository()
    identifier = str(review_id)
    snapshot = repository.get(identifier)
    if not repository.claim(identifier):
        return repository.get(identifier)  # Never duplicate a completed/error/in-flight paid call.
    try:
        root = authorized_root(snapshot.repository, snapshot.repository_root)
        parsed = parse_diff(snapshot.diff)
        check_egress(root, snapshot.diff, parsed)
        with audit_progress(
            lambda audit, analysis: repository.save_progress(identifier, audit, analysis)
        ):
            result = analyze_parsed(parsed)
    except (AnalysisError, DiffParseError, InspectionError) as exc:
        repository.finish(
            identifier,
            None,
            RecoverableError(code=exc.code, message=str(exc)),
            getattr(exc, "audit", None),
        )
    except Exception:
        repository.finish(
            identifier,
            None,
            RecoverableError(
                code="analysis_failed",
                message="El análisis falló; la instantánea se conserva.",
            ),
        )
    else:
        partial = result.audit is not None and result.audit.status != "completed"
        repository.finish(
            identifier,
            result,
            RecoverableError(code="audit_partial", message="Partial audit; see batch coverage.")
            if partial
            else None,
        )
    return repository.get(identifier)


@router.post("/{review_id}/recovery", response_model=ReviewDetail)
def recover_review(review_id: UUID4, data: RecoveryRequest, request: Request) -> ReviewDetail:
    # Explicit same-origin browser gate, in addition to loopback/Host/JSON/marker middleware.
    # This is not authentication: a local program can forge Origin. No MCP retry tool exists.
    if request.headers.get("origin") != web_url():
        raise ReviewError("human_recovery_origin_required", "Use the local web interface.", 403)
    repository = get_review_repository()
    original = repository.get(str(review_id), include_recovery=False)
    parsed, groups = reconstruct_batches(original)

    def preflight():
        root = authorized_root(original.repository, original.repository_root)
        check_egress(root, original.diff, parsed)

    preflight()
    return execute_recovery(repository, original, data, parsed, groups, preflight)
