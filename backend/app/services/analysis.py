"""Analysis orchestration shared by the HTTP and MCP adapters."""

from dataclasses import asdict

from app.analysis_models import AnalysisResponse
from app.models import ParseResponse
from app.services.diff_parser import ParsedDiff
from app.services.model_client import MODEL, review_diff
from app.services.reference_validator import check_findings


def analyze_parsed(parsed: ParsedDiff) -> AnalysisResponse:
    review = review_diff(parsed)
    return AnalysisResponse(
        model=MODEL,
        summary=review.summary,
        findings=check_findings(parsed, review),
        parsed_diff=ParseResponse.model_validate(asdict(parsed)),
    )
