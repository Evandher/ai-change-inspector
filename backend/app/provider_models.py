"""Allowlisted diagnostics only: never retain provider bodies or partial output."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    response_id: str | None = None
    request_id: str | None = None
    incomplete_details: dict[str, str | None] | None = None
    incomplete_details_present: bool | None = None
    incomplete_reason: str | None = None
    provider_error_code: str | None = None
    http_status: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    max_output_tokens: int = 8192
    outcome: Literal[
        "unknown", "completed", "budget", "incomplete", "provider", "timeout", "schema", "preflight"
    ] = "unknown"


class AuditBatch(BaseModel):
    batch_id: str
    file_ids: list[str]
    hunk_ids: list[str]
    status: Literal["pending", "completed", "failed", "incomplete"] = "pending"
    error_code: str | None = None
    diagnostics: ProviderDiagnostic | None = None
    payload_sha256: str | None = None
    payload_version: Literal[1] | None = None
    payload_bytes: int
    original_payload_bytes: int


class AuditRun(BaseModel):
    version: Literal[1] = 1
    status: Literal["pending", "analyzing", "completed", "partial", "incomplete"] = "pending"
    max_requests: int
    request_count: int = 0
    batches: list[AuditBatch] = Field(default_factory=list)
    # Coverage is by immutable hunk IDs, not by inferred whole-file correctness.
    completed_hunk_ids: list[str] = Field(default_factory=list)
    unanalyzed_hunk_ids: list[str] = Field(default_factory=list)
    metadata_only_file_ids: list[str] = Field(default_factory=list)
