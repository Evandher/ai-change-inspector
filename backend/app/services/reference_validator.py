"""Check references against parser output only; never read repository files."""

from app.analysis_models import CheckedFinding, ModelReview, Reference, ReferenceCheck
from app.services.diff_parser import ParsedDiff


def check_reference(parsed: ParsedDiff, reference: Reference) -> ReferenceCheck:
    def result(reason: str, diff_line: int | None = None) -> ReferenceCheck:
        return ReferenceCheck(
            reference=reference,
            status="valid" if reason == "matched" else "invalid",
            reason=reason,
            diff_line=diff_line,
        )

    file = next((file for file in parsed.files if file.file_id == reference.file_id), None)
    if file is None:
        return result("file_not_found")
    hunk = next((hunk for hunk in file.hunks if hunk.hunk_id == reference.hunk_id), None)
    if hunk is None:
        return result("hunk_not_found")
    path = file.old_path if reference.side == "old" else file.new_path
    if reference.path != path:
        return result("path_mismatch")
    if reference.line_start < 1 or reference.line_end < reference.line_start:
        return result("invalid_range")
    # Select existing lines, never iterate a model-supplied (potentially enormous) range.
    selected = []
    numbers = []
    for line in hunk.lines:
        number = line.old_line if reference.side == "old" else line.new_line
        if number is not None and reference.line_start <= number <= reference.line_end:
            selected.append(line)
            numbers.append(number)
    count = reference.line_end - reference.line_start + 1
    if (
        not selected
        or len(numbers) != count
        or numbers[0] != reference.line_start
        or numbers[-1] != reference.line_end
    ):
        return result("line_not_found")
    if reference.quote != "\n".join(line.content for line in selected):
        return result("quote_mismatch")
    return result("matched", selected[0].diff_line)


def check_findings(parsed: ParsedDiff, review: ModelReview) -> list[CheckedFinding]:
    findings = []
    for hypothesis in review.findings:
        checks = [check_reference(parsed, reference) for reference in hypothesis.references]
        findings.append(
            CheckedFinding(
                hypothesis=hypothesis,
                reference_checks=checks,
                all_references_valid=all(check.status == "valid" for check in checks),
            )
        )
    return findings
