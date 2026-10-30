"""Human annotations are independent from immutable provider findings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.analysis_models import CheckedFinding
from app.inspection_models import RecoverableError

Decision = Literal["request_changes", "accept_risk", "dismiss"]


class FeedbackWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    comment: str = Field(default="", strict=True, max_length=4000)


class HumanFeedback(BaseModel):
    finding_index: int
    decision: Decision | None = None
    comment: str = ""
    updated_at: str | None = None


class FeedbackFinding(HumanFeedback):
    finding: CheckedFinding


class ReviewFeedback(BaseModel):
    review_id: str
    repository: str
    repository_root: str
    review_url: str
    analysis_status: Literal["pending", "analyzing", "completed", "error"]
    parent_review_id: str | None
    child_review_ids: list[str]
    items: list[FeedbackFinding]
    pending_count: int


class FeedbackResult(BaseModel):
    status: Literal["available", "blocked", "error"]
    repository: str
    review_id: str
    feedback: ReviewFeedback | None = None
    error: RecoverableError | None = None
