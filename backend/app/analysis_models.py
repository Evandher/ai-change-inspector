"""Model hypotheses and independent structural checks have separate contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ParseResponse

ShortText = Annotated[str, Field(min_length=1, max_length=2000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Reference(StrictModel):
    file_id: ShortText
    hunk_id: ShortText
    path: ShortText
    side: Literal["old", "new"]
    line_start: int
    line_end: int
    quote: Annotated[str, Field(max_length=8000)]


class ModelFinding(StrictModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    severity: Literal["low", "medium", "high", "critical"]
    explanation: ShortText
    references: Annotated[list[Reference], Field(min_length=1, max_length=5)]
    suggested_tests: Annotated[list[ShortText], Field(min_length=1, max_length=5)]


class ModelReview(StrictModel):
    summary: ShortText
    findings: Annotated[list[ModelFinding], Field(max_length=20)]


class ReferenceCheck(StrictModel):
    reference: Reference
    status: Literal["valid", "invalid"]
    reason: Literal[
        "matched",
        "file_not_found",
        "hunk_not_found",
        "path_mismatch",
        "invalid_range",
        "line_not_found",
        "quote_mismatch",
    ]
    diff_line: int | None


class CheckedFinding(StrictModel):
    hypothesis: ModelFinding
    reference_checks: list[ReferenceCheck]
    all_references_valid: bool


class AnalysisResponse(StrictModel):
    model: Literal["muse-spark-1.3"]
    summary: str
    findings: list[CheckedFinding]
    parsed_diff: ParseResponse
