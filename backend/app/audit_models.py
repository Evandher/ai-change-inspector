"""Additive, non-authenticated provenance and bounded capture metadata."""

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgentSource = Literal["unknown", "muse_code", "codex", "claude_code", "other"]
ExclusionReason = Literal[
    "policy", "sensitive", "binary", "too_large", "unsafe", "encoding", "budget"
]


class CaptureCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    include_untracked: bool = False
    untracked_seen: int | None = Field(default=None, ge=0, le=10000)
    included_untracked: list[str] = Field(default_factory=list, max_length=500)
    exclusions: dict[ExclusionReason, Annotated[int, Field(ge=0, le=10000)]] = Field(
        default_factory=dict
    )

    @field_validator("included_untracked")
    @classmethod
    def safe_paths(cls, values):
        for value in values:
            path = PurePosixPath(value)
            if (
                not value
                or len(value) > 512
                or path.is_absolute()
                or ".." in path.parts
                or ":" in value
                or "\\" in value
                or any(ord(c) < 32 for c in value)
            ):
                raise ValueError("Unsafe coverage path")
        if len(set(values)) != len(values):
            raise ValueError("Duplicate coverage path")
        return values
