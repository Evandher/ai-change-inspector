from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.analysis_models import CheckedFinding

ChangeScope = Literal["staged", "unstaged"]


class InspectionError(Exception):
    def __init__(self, code: str, message: str, *, blocked: bool = False):
        super().__init__(message)
        self.code = code
        self.blocked = blocked


class RecoverableError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    recoverable: bool = True


class InspectionAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["muse-spark-1.3"]
    summary: str
    findings: list[CheckedFinding]


class InspectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "no_changes", "blocked", "error"]
    repository: str
    scope: ChangeScope
    untracked_policy: Literal["excluded"] = "excluded"
    analysis: InspectionAnalysis | None = None
    error: RecoverableError | None = None
