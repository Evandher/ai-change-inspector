from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import ErrorResponse, HealthResponse, ParseRequest, ParseResponse
from app.services.diff_parser import DiffParseError, parse_diff

app = FastAPI(title="AI Change Inspector", version="0.1.0")


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
