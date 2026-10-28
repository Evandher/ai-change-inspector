from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diff: str = Field(strict=True, description="Unified Git diff, at most 1 MiB in UTF-8.")


class LineResponse(BaseModel):
    kind: Literal["context", "addition", "deletion"]
    content: str
    old_line: int | None
    new_line: int | None
    diff_line: int
    no_newline: bool


class HunkResponse(BaseModel):
    hunk_id: str
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[LineResponse]


class FileResponse(BaseModel):
    file_id: str
    old_path: str | None
    new_path: str | None
    change_type: Literal["added", "deleted", "modified", "renamed", "copied"]
    is_binary: bool
    metadata: list[str]
    hunks: list[HunkResponse]
    additions: int
    deletions: int


class ParseResponse(BaseModel):
    files: list[FileResponse]
    additions: int
    deletions: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    line: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: Literal["ok"]
