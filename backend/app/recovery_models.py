"""Recovery metadata is separate from immutable original review results."""

from typing import Annotated, Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.analysis_models import CheckedFinding
from app.provider_models import AuditRun, ProviderDiagnostic

BatchId = Annotated[str, Field(pattern=r"^batch-[1-9][0-9]{0,4}$")]


class RecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID4
    batch_ids: list[BatchId] = Field(min_length=1, max_length=8)
    expected_version: int = Field(ge=0, strict=True)
    expected_output_budget: int = Field(ge=16, le=8192, strict=True)
    confirm_paid: Literal[True]


class RecoveryAttempt(BaseModel):
    attempt_id: str
    request_id: str
    batch_id: str
    number: int
    status: Literal["pending", "running", "completed", "failed", "incomplete", "interrupted"]
    created_at: str
    started_at: str | None
    finished_at: str | None
    output_budget: int
    error_code: str | None
    diagnostics: ProviderDiagnostic | None


class RecoveryView(BaseModel):
    supported: bool = False
    blocked_reason: str | None = None
    version: int = 0
    active_request_id: str | None = None
    eligible_batch_ids: list[str] = Field(default_factory=list)
    batch_blockers: dict[str, str] = Field(default_factory=dict)
    attempts: list[RecoveryAttempt] = Field(default_factory=list)
    max_calls_per_action: int = 0
    max_per_batch: int = 0
    max_per_review: int = 0
    remaining_review: int = 0
    output_budget: int | None = None
    original_audit: AuditRun | None = None
    original_status: str
    original_finished_at: str | None


class RecoveryResult(BaseModel):
    summary: str
    findings: list[CheckedFinding]
