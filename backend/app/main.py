from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.analysis_models import AnalysisResponse
from app.models import ErrorResponse, HealthResponse, ParseRequest, ParseResponse
from app.services.diff_parser import DiffParseError, parse_diff
from app.services.model_client import MODEL, AnalysisError, review_diff
from app.services.reference_validator import check_findings

app = FastAPI(title="AI Change Inspector", version="0.2.0")


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
                "message": "Expected JSON with a string 'diff' only.",
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
    parsed = parse_diff(request.diff)
    review = review_diff(parsed)
    return AnalysisResponse(
        model=MODEL,
        summary=review.summary,
        findings=check_findings(parsed, review),
        parsed_diff=ParseResponse.model_validate(asdict(parsed)),
    )
