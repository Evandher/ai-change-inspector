from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.diff_parser import MAX_DIFF_BYTES, DiffParseError, parse_diff

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "diffs"
SIMPLE = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"


def test_modified_example():
    result = parse_diff((EXAMPLES / "modified.diff").read_text())
    assert (result.additions, result.deletions) == (2, 1)
    file = result.files[0]
    assert file.old_path == file.new_path == "src/greeting.py"
    assert file.change_type == "modified"
    lines = file.hunks[0].lines
    assert [(line.old_line, line.new_line) for line in lines] == [
        (1, 1),
        (2, None),
        (None, 2),
        (None, 3),
        (3, 4),
    ]
    assert lines[-1].content == ""
    assert lines[0].diff_line == 6


def test_multiple_files_example():
    result = parse_diff((EXAMPLES / "multiple-files.diff").read_text())
    assert [file.change_type for file in result.files] == ["modified", "added", "deleted"]
    assert (result.additions, result.deletions) == (3, 2)
    assert result.files[1].old_path is None
    assert result.files[2].new_path is None


def test_metadata_example():
    files = parse_diff((EXAMPLES / "metadata.diff").read_text()).files
    assert [file.change_type for file in files] == ["renamed", "copied", "modified", "modified"]
    assert files[0].new_path == "new name.txt"
    assert files[-1].is_binary
    assert not any(file.hunks for file in files)
    assert files[2].metadata == ("old mode 100644", "new mode 100755")


def test_ids_are_deterministic_and_normalize_line_endings():
    first = parse_diff(SIMPLE)
    assert first == parse_diff(SIMPLE)
    assert first == parse_diff(SIMPLE.replace("\n", "\r\n"))
    assert first == parse_diff(SIMPLE.rstrip("\n"))
    with pytest.raises(FrozenInstanceError):
        first.additions = 10


def test_ids_are_unique_and_independent_of_unrelated_files():
    first = parse_diff(SIMPLE).files[0]
    duplicates = parse_diff(SIMPLE + SIMPLE).files
    assert duplicates[0].file_id != duplicates[1].file_id
    assert duplicates[0].hunks[0].hunk_id != duplicates[1].hunks[0].hunk_id
    other = SIMPLE.replace("a.txt", "other.txt")
    moved = parse_diff(other + SIMPLE).files[1]
    assert moved.file_id == first.file_id
    assert moved.hunks[0].hunk_id == first.hunks[0].hunk_id
    assert parse_diff(SIMPLE.replace("+new", "+changed")).files[0].file_id != first.file_id


def test_multiple_hunks_and_literal_header_content():
    text = SIMPLE + "@@ -5 +5 @@ section\n--- literal\n+++ literal\n"
    hunks = parse_diff(text).files[0].hunks
    assert len(hunks) == 2
    assert hunks[0].hunk_id != hunks[1].hunk_id
    assert hunks[1].lines[0].content == "-- literal"


def test_no_newline_markers():
    text = SIMPLE.replace("-old\n", "-old\n\\ No newline at end of file\n")
    text += "\\ No newline at end of file\n"
    lines = parse_diff(text).files[0].hunks[0].lines
    assert all(line.no_newline for line in lines)


def test_quoted_utf8_octal_paths():
    text = (
        'diff --git "a/caf\\303\\251.txt" "b/caf\\303\\251.txt"\n'
        '--- "a/caf\\303\\251.txt"\n+++ "b/caf\\303\\251.txt"\n'
        "@@ -1 +1 @@\n-a\n+b\n"
    )
    assert parse_diff(text).files[0].new_path == "café.txt"


def test_quoted_tabs_and_spaces():
    text = SIMPLE.replace("a/a.txt", '"a/my\\tfile.txt"')
    text = text.replace("b/a.txt", '"b/my\\tfile.txt"')
    assert parse_diff(text).files[0].new_path == "my\tfile.txt"
    assert parse_diff(SIMPLE.replace("a.txt", "my file.txt")).files[0].new_path == "my file.txt"


def test_binary_payload_is_opaque():
    text = "diff --git a/image b/image\nGIT binary patch\nliteral 2\nopaque\n\n"
    file = parse_diff(text).files[0]
    assert file.is_binary and file.hunks == ()


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty_diff"),
        (" \n", "empty_diff"),
        ("not a diff", "invalid_header"),
        ("diff --cc a.txt\n", "unsupported_format"),
        (SIMPLE.replace("@@ -1 +1 @@", "@@@ -1 -1 +1 @@@"), "unsupported_format"),
        (SIMPLE.replace("@@ -1 +1 @@", "@@ broken @@"), "invalid_hunk"),
        (SIMPLE.replace("@@ -1 +1 @@", "@@ -0 +1 @@"), "invalid_range"),
        (SIMPLE.replace("@@ -1 +1 @@", "@@ -1,2 +1,2 @@"), "hunk_count_mismatch"),
        (SIMPLE + "+extra\n", "unexpected_line"),
        (SIMPLE.replace("-old\n", ""), "hunk_count_mismatch"),
        (SIMPLE.replace("+++ b/a.txt\n", ""), "invalid_hunk"),
        (SIMPLE.replace("-old", "\\ No newline at end of file"), "invalid_marker"),
        (SIMPLE + "\\ No newline at end of file\n\\ No newline at end of file\n", "invalid_marker"),
        (SIMPLE.replace("a/a.txt", '"a/\\q"'), "invalid_path"),
        (SIMPLE.replace("a/a.txt", '"a/\\777"'), "invalid_path"),
        (SIMPLE.replace("a/a.txt", '"a/\\377"'), "invalid_path"),
        (SIMPLE.replace("-old", "-\x00"), "invalid_encoding"),
        (SIMPLE.replace("-old", "-\ud800"), "invalid_encoding"),
        ("diff --git a/a b/a\n", "empty_file"),
        ("diff --git a/a b/a\nrename from a\n", "invalid_metadata"),
        ("diff --git a/a b/a\n--- a/a\n", "invalid_header"),
        (SIMPLE + "@@ -1 +1 @@\n-x\n+y\n", "invalid_range"),
    ],
)
def test_invalid_diffs(text, code):
    with pytest.raises(DiffParseError) as error:
        parse_diff(text)
    assert error.value.code == code


def test_truncated_fixture_reports_line():
    with pytest.raises(DiffParseError) as error:
        parse_diff((EXAMPLES / "invalid-truncated.diff").read_text())
    assert error.value.code == "hunk_count_mismatch"
    assert error.value.line == 6


def test_utf8_size_limit_inclusive():
    prefix = "diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -0,0 +1 @@\n+"
    text = prefix + "x" * (MAX_DIFF_BYTES - len(prefix.encode()) - 1) + "\n"
    assert len(text.encode()) == MAX_DIFF_BYTES
    assert parse_diff(text).additions == 1
    with pytest.raises(DiffParseError, match="1 MiB"):
        parse_diff(text + "x")
    multibyte = prefix + "é" * (MAX_DIFF_BYTES // 2) + "\n"
    assert len(multibyte) < MAX_DIFF_BYTES
    with pytest.raises(DiffParseError) as error:
        parse_diff(multibyte)
    assert error.value.code == "diff_too_large"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (SIMPLE.replace("@@ -1 +1 @@", "@@ -" + "9" * 5000 + " +1 @@"), "invalid_hunk"),
        ("diff --git a/a b/a\nnew file mode invalid\n", "invalid_metadata"),
        ("diff --git a/a b/a\nsimilarity index 101%\n", "invalid_metadata"),
        ("diff --git a/a b/a\n--- a/a\n+++ b/a\n", "invalid_hunk"),
        (SIMPLE.replace("a/a.txt", "a/"), "invalid_path"),
        (SIMPLE.replace("--- a/a.txt", "--- /dev/null"), "invalid_range"),
        (SIMPLE.replace("+++ b/a.txt", "+++ /dev/null"), "invalid_range"),
        (
            SIMPLE.replace("@@ -1 +1 @@", "@@ -1,2 +1 @@").replace(
                "-old\n", "-old\n\\ No newline at end of file\n-another\n"
            ),
            "invalid_marker",
        ),
    ],
)
def test_malformed_edge_cases(text, code):
    with pytest.raises(DiffParseError) as error:
        parse_diff(text)
    assert error.value.code == code
