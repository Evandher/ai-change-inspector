from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi import Path as ApiPath
from pydantic import UUID4

from app.feedback_models import FeedbackWrite, HumanFeedback, ReviewFeedback
from app.inspection_models import InspectionError, RecoverableError
from app.local_settings import database_path, web_repositories, web_url
from app.models import ParseResponse
from app.review_models import ReviewCreate, ReviewDetail, ReviewError, ReviewPage
from app.review_store import ReviewRepository
from app.services.analysis import analyze_parsed
from app.services.diff_parser import DiffParseError, parse_diff
from app.services.egress_guard import check_egress
from app.services.model_client import AnalysisError

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
    return get_review_repository().create(request, ParseResponse.model_validate(asdict(parsed)))


@router.get("", response_model=ReviewPage)
def list_reviews(
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0
) -> ReviewPage:
    return get_review_repository().list(limit, offset)


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(review_id: UUID4) -> ReviewDetail:
    return get_review_repository().get(str(review_id))


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
        result = analyze_parsed(parsed)
    except (AnalysisError, DiffParseError, InspectionError) as exc:
        repository.finish(identifier, None, RecoverableError(code=exc.code, message=str(exc)))
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
        repository.finish(identifier, result, None)
    return repository.get(identifier)
