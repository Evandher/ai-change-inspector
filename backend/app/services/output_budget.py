"""Operator-only output budgets. No inferred provider limits or automatic increases."""

import os

DEFAULT_OUTPUT_TOKENS = 8192
# Higher compatibility has not been established for the hosted model/endpoint.
CONFIRMED_OUTPUT_CEILING = 8192


def output_budget(requested: int | None = None) -> int:
    from app.services.model_client import AnalysisError

    try:
        ceiling = int(os.environ.get("INSPECTOR_OUTPUT_TOKEN_CEILING", "8192"))
        value = (
            int(os.environ.get("INSPECTOR_MAX_OUTPUT_TOKENS", "8192"))
            if requested is None
            else requested
        )
        valid = type(value) is int and 16 <= value <= ceiling <= CONFIRMED_OUTPUT_CEILING
    except ValueError:
        valid = False
    if not valid:
        raise AnalysisError(
            "invalid_output_budget",
            "Output budget must satisfy 16 <= requested <= ceiling <= 8192.",
            503,
        )
    return value
