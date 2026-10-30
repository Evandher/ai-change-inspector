from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.analysis_models import AnalysisResponse
from app.inspection_models import InspectionError
from app.local_access import LocalAccessMiddleware
from app.models import ErrorResponse, HealthResponse, ParseRequest, ParseResponse
from app.review_api import get_review_repository
from app.review_api import router as review_router
from app.review_models import ReviewError
from app.services.analysis import analyze_parsed
from app.services.diff_parser import DiffParseError, parse_diff
from app.services.model_client import AnalysisError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_review_repository().recover_interrupted()
    yield


app = FastAPI(title="AI Change Inspector", version="0.5.0", lifespan=lifespan)
app.add_middleware(LocalAccessMiddleware)
app.include_router(review_router)


@app.exception_handler(ReviewError)
@app.exception_handler(InspectionError)
async def review_error_handler(
    _request: Request, exc: ReviewError | InspectionError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code if isinstance(exc, ReviewError) else 403,
        content={"error": {"code": exc.code, "message": str(exc), "line": None}},
    )


@app.exception_handler(AnalysisError)
async def analysis_error_handler(_request: Request, exc: AnalysisError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": str(exc), "line": None},
        },
    )


@app.exception_handler(DiffParseError)
async def parser_error_handler(_request: Request, exc: DiffParseError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {"code": exc.code, "message": str(exc), "line": exc.line},
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_request",
                "message": "Solicitud de revisión no válida."
                if _request.url.path.startswith("/api/reviews")
                else "Expected JSON with a string 'diff' only.",
                "line": None,
            },
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/api/diff/parse", response_model=ParseResponse, responses={422: {"model": ErrorResponse}}
)
def parse(request: ParseRequest) -> ParseResponse:
    return ParseResponse.model_validate(asdict(parse_diff(request.diff)))


@app.post(
    "/api/diff/analyze",
    response_model=AnalysisResponse,
    responses={code: {"model": ErrorResponse} for code in (413, 422, 502, 503, 504)},
)
def analyze(request: ParseRequest) -> AnalysisResponse:
    return analyze_parsed(parse_diff(request.diff))
