from typing import Literal
from uuid import uuid4

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.analysis_models import AnalysisResponse
from app.feedback_models import HumanFeedback
from app.inspection_models import ChangeScope, RecoverableError
from app.models import ParseResponse

ReviewStatus = Literal["pending", "analyzing", "completed", "error"]


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: UUID4 = Field(default_factory=uuid4)
    repository: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    repository_root: str = Field(strict=True, max_length=4096)
    scope: ChangeScope
    diff: str = Field(strict=True)
    parent_review_id: UUID4 | None = None


class ReviewSummary(BaseModel):
    review_id: str
    repository: str
    repository_root: str
    origin: Literal["mcp"]
    scope: ChangeScope
    created_at: str
    finished_at: str | None
    status: ReviewStatus
    diff_sha256: str
    review_url: str
    error: RecoverableError | None


class ReviewDetail(ReviewSummary):
    diff: str
    parsed_diff: ParseResponse
    analysis: AnalysisResponse | None
    parent_review_id: str | None = None
    child_review_ids: list[str] = Field(default_factory=list)
    feedback: list[HumanFeedback] = Field(default_factory=list)


class ReviewPage(BaseModel):
    items: list[ReviewSummary]
    total: int


class ReviewError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
