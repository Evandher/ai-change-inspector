"""Pure unified Git diff parser. No framework or I/O dependencies."""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Literal

MAX_DIFF_BYTES = 1024 * 1024
HUNK_HEADER = re.compile(
    r"^@@ -([0-9]{1,9})(?:,([0-9]{1,9}))? \+([0-9]{1,9})(?:,([0-9]{1,9}))? @@(?: .*)?$"
)
QUOTED_PATH = re.compile(r'"(?:[^"\\]|\\.)*"')
METADATA = re.compile(
    r"(?:(?:new file mode|deleted file mode|old mode|new mode) [0-7]{6}"
    r"|index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?"
    r"|(?:dis)?similarity index (?:100|[0-9]{1,2})%)"
)


class DiffParseError(ValueError):
    def __init__(self, code: str, message: str, line: int | None = None):
        super().__init__(message)
        self.code = code
        self.line = line


@dataclass(frozen=True)
class DiffLine:
    kind: Literal["context", "addition", "deletion"]
    content: str
    old_line: int | None
    new_line: int | None
    diff_line: int
    no_newline: bool = False


@dataclass(frozen=True)
class Hunk:
    hunk_id: str
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[DiffLine, ...]


@dataclass(frozen=True)
class DiffFile:
    file_id: str
    old_path: str | None
    new_path: str | None
    change_type: Literal["added", "deleted", "modified", "renamed", "copied"]
    is_binary: bool
    metadata: tuple[str, ...]
    hunks: tuple[Hunk, ...]
    additions: int
    deletions: int


@dataclass(frozen=True)
class ParsedDiff:
    files: tuple[DiffFile, ...]
    additions: int
    deletions: int


def _id(prefix: str, parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(payload.encode()).hexdigest()}"


def _path(value: str, line: int, strip_prefix: bool = True) -> str | None:
    if value.startswith('"'):
        # Git quotes UTF-8 bytes using C escapes, including octal escapes.
        if not QUOTED_PATH.fullmatch(value):
            raise DiffParseError("invalid_path", "Malformed quoted Git path.", line)
        data = bytearray()
        index = 1
        escapes = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}
        while index < len(value) - 1:
            char = value[index]
            if char != "\\":
                data.extend(char.encode("utf-8"))
                index += 1
                continue
            index += 1
            char = value[index]
            if char in escapes:
                data.append(escapes[char])
                index += 1
            elif char in "01234567":
                match = re.match(r"[0-7]{1,3}", value[index:])
                assert match is not None
                number = int(match[0], 8)
                if number > 255:
                    raise DiffParseError("invalid_path", "Invalid octal path escape.", line)
                data.append(number)
                index += len(match[0])
            else:
                raise DiffParseError("invalid_path", "Unknown Git path escape.", line)
        try:
            value = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DiffParseError("invalid_path", "Paths must be UTF-8.", line) from exc
    if not value or "\x00" in value:
        raise DiffParseError("invalid_path", "Empty or NUL-containing path.", line)
    if value == "/dev/null":
        return None
    if strip_prefix and value.startswith(("a/", "b/")):
        value = value[2:]
    if not value:
        raise DiffParseError("invalid_path", "Empty path after Git prefix.", line)
    return value


def _git_paths(header: str, line: int) -> tuple[str | None, str | None]:
    value = header[len("diff --git ") :]
    if value.startswith('"'):
        match = QUOTED_PATH.match(value)
        if match is None or not value[match.end() :].startswith(" "):
            raise DiffParseError("invalid_header", "Malformed diff --git header.", line)
        old, new = match[0], value[match.end() + 1 :]
    else:
        # Git leaves spaces unquoted. Default b/ prefix disambiguates the two paths.
        boundary = value.find(' "b/')
        if boundary < 0:
            boundary = value.find(" b/")
        if boundary < 0:
            raise DiffParseError("invalid_header", "Expected Git a/ and b/ path prefixes.", line)
        old, new = value[:boundary], value[boundary + 1 :]
    return _path(old, line), _path(new, line)


def _hunk(rows: list[str], index: int, offset: int) -> tuple[Hunk, int]:
    match = HUNK_HEADER.fullmatch(rows[index])
    if match is None:
        raise DiffParseError("invalid_hunk", "Malformed unified hunk header.", offset + index + 1)
    old_start, old_count, new_start, new_count = (
        int(value) if value is not None else 1 for value in match.groups()
    )
    if (old_count and old_start == 0) or (new_count and new_start == 0):
        raise DiffParseError(
            "invalid_range", "Nonempty ranges start at line 1 or later.", offset + index + 1
        )
    header = rows[index]
    index += 1
    old_seen = new_seen = 0
    old_closed = new_closed = False
    lines: list[DiffLine] = []
    while index < len(rows):
        row = rows[index]
        number = offset + index + 1
        if row == "\\ No newline at end of file":
            if not lines or lines[-1].no_newline:
                raise DiffParseError(
                    "invalid_marker", "Newline marker has no preceding line.", number
                )
            lines[-1] = replace(lines[-1], no_newline=True)
            old_closed |= lines[-1].old_line is not None
            new_closed |= lines[-1].new_line is not None
            index += 1
            continue
        if old_seen == old_count and new_seen == new_count:
            break
        if not row or row[0] not in " +-":
            raise DiffParseError(
                "hunk_count_mismatch", "Hunk ended before its declared counts.", number
            )
        prefix = row[0]
        if (old_closed and prefix != "+") or (new_closed and prefix != "-"):
            raise DiffParseError("invalid_marker", "Content follows an end-of-file marker.", number)
        lines.append(
            DiffLine(
                kind={" ": "context", "+": "addition", "-": "deletion"}[prefix],
                content=row[1:],
                old_line=old_start + old_seen if prefix != "+" else None,
                new_line=new_start + new_seen if prefix != "-" else None,
                diff_line=number,
            )
        )
        old_seen += prefix != "+"
        new_seen += prefix != "-"
        if old_seen > old_count or new_seen > new_count:
            raise DiffParseError("hunk_count_mismatch", "Hunk exceeds its declared counts.", number)
        index += 1
    if (old_seen, new_seen) != (old_count, new_count):
        raise DiffParseError("hunk_count_mismatch", "Truncated hunk.", offset + index + 1)
    return Hunk("", header, old_start, old_count, new_start, new_count, tuple(lines)), index


def _file(rows: list[str], offset: int, file_id: str) -> DiffFile:
    old_path, new_path = _git_paths(rows[0], offset + 1)
    metadata: list[str] = []
    hunks: list[Hunk] = []
    binary = False
    binary_payload = False
    change_type = "modified"
    old_header = new_header = False
    rename_from = rename_to = copy_from = copy_to = False
    index = 1
    while index < len(rows):
        row = rows[index]
        number = offset + index + 1
        if row.startswith("@@@"):
            raise DiffParseError(
                "unsupported_format", "Combined merge diffs are unsupported.", number
            )
        if row.startswith("@@"):
            if binary or not (old_header and new_header):
                raise DiffParseError("invalid_hunk", "Hunk requires text file headers.", number)
            hunk_start = index
            hunk, index = _hunk(rows, index, offset)
            if hunks:
                previous = hunks[-1]
                if (
                    hunk.old_start < previous.old_start + previous.old_count
                    or hunk.new_start < previous.new_start + previous.new_count
                ):
                    raise DiffParseError("invalid_range", "Overlapping or unordered hunks.", number)
            hunk_id = _id("hunk", [file_id, len(hunks), rows[hunk_start:index]])
            hunks.append(replace(hunk, hunk_id=hunk_id))
            continue
        if binary_payload:
            index += 1
            continue
        if row.startswith("--- ") and not old_header and not hunks:
            old_path = _path(row[4:], number)
            old_header = True
        elif row.startswith("+++ ") and old_header and not new_header and not hunks:
            new_path = _path(row[4:], number)
            new_header = True
        elif hunks or old_header:
            raise DiffParseError("unexpected_line", "Unexpected line outside a hunk.", number)
        elif row.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            for prefix in ("rename from ", "rename to ", "copy from ", "copy to "):
                if row.startswith(prefix):
                    value = _path(row[len(prefix) :], number, strip_prefix=False)
                    if prefix.endswith("from "):
                        old_path = value
                    else:
                        new_path = value
                    rename_from |= prefix == "rename from "
                    rename_to |= prefix == "rename to "
                    copy_from |= prefix == "copy from "
                    copy_to |= prefix == "copy to "
                    break
            metadata.append(row)
        elif row.startswith(
            (
                "new file mode ",
                "deleted file mode ",
                "old mode ",
                "new mode ",
                "index ",
                "similarity index ",
                "dissimilarity index ",
            )
        ):
            if not METADATA.fullmatch(row):
                raise DiffParseError("invalid_metadata", "Malformed Git change metadata.", number)
            metadata.append(row)
            if row.startswith("new file mode "):
                change_type, old_path = "added", None
            elif row.startswith("deleted file mode "):
                change_type, new_path = "deleted", None
        elif row == "GIT binary patch" or (
            row.startswith("Binary files ") and row.endswith(" differ")
        ):
            binary = True
            binary_payload = row == "GIT binary patch"
            metadata.append(row)
        else:
            raise DiffParseError("unexpected_line", "Unsupported or malformed diff line.", number)
        index += 1
    if old_header != new_header:
        raise DiffParseError("invalid_header", "Expected paired --- and +++ headers.", offset + 1)
    if old_header and not hunks:
        raise DiffParseError("invalid_hunk", "Text headers must be followed by a hunk.", offset + 1)
    if old_path is None and any(hunk.old_count for hunk in hunks):
        raise DiffParseError("invalid_range", "Added file has old-side content.", offset + 1)
    if new_path is None and any(hunk.new_count for hunk in hunks):
        raise DiffParseError("invalid_range", "Deleted file has new-side content.", offset + 1)
    if change_type == "added" and old_path is not None:
        raise DiffParseError(
            "invalid_metadata", "Added file must use /dev/null as old path.", offset + 1
        )
    if change_type == "deleted" and new_path is not None:
        raise DiffParseError(
            "invalid_metadata", "Deleted file must use /dev/null as new path.", offset + 1
        )
    if rename_from != rename_to or copy_from != copy_to or (rename_from and copy_from):
        raise DiffParseError(
            "invalid_metadata", "Incomplete or conflicting rename/copy metadata.", offset + 1
        )
    if rename_from:
        change_type = "renamed"
    elif copy_from:
        change_type = "copied"
    elif old_path is None:
        change_type = "added"
    elif new_path is None:
        change_type = "deleted"
    if old_path is None and new_path is None:
        raise DiffParseError("invalid_path", "Both file paths cannot be /dev/null.", offset + 1)
    if not hunks and not binary and not metadata:
        raise DiffParseError("empty_file", "File has no hunks or change metadata.", offset + 1)
    return DiffFile(
        file_id,
        old_path,
        new_path,
        change_type,
        binary,
        tuple(metadata),
        tuple(hunks),
        sum(line.kind == "addition" for hunk in hunks for line in hunk.lines),
        sum(line.kind == "deletion" for hunk in hunks for line in hunk.lines),
    )


def parse_diff(text: str) -> ParsedDiff:
    """Parse default-prefix `git diff` patch text or raise a structured error.

    IDs hash normalized file content plus duplicate occurrence; hunk IDs also
    include their file ID. No identifiers depend on other files' positions.
    """
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise DiffParseError("invalid_encoding", "Diff must contain valid UTF-8 text.") from exc
    if size > MAX_DIFF_BYTES:
        raise DiffParseError("diff_too_large", "Diff exceeds the 1 MiB UTF-8 limit.")
    if not text.strip():
        raise DiffParseError("empty_diff", "Paste a nonempty Git diff.")
    if "\x00" in text:
        raise DiffParseError("invalid_encoding", "NUL bytes are unsupported.")
    rows = text.replace("\r\n", "\n").split("\n")
    if rows[-1] == "":
        rows.pop()
    starts = []
    for index, row in enumerate(rows):
        if row.startswith(("diff --cc ", "diff --combined ")):
            raise DiffParseError(
                "unsupported_format", "Combined merge diffs are unsupported.", index + 1
            )
        if row.startswith("diff --git "):
            starts.append(index)
    if not starts or starts[0] != 0:
        raise DiffParseError("invalid_header", "Expected a diff --git header at the start.", 1)
    files = []
    occurrences: dict[str, int] = {}
    for start, end in zip(starts, [*starts[1:], len(rows)], strict=True):
        block = rows[start:end]
        fingerprint = _id("content", block)
        occurrence = occurrences.get(fingerprint, 0)
        occurrences[fingerprint] = occurrence + 1
        files.append(_file(block, start, _id("file", [fingerprint, occurrence])))
    return ParsedDiff(
        tuple(files), sum(file.additions for file in files), sum(file.deletions for file in files)
    )
