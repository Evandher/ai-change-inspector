"""Lossless compact transport. Canonical parser data is never modified."""

import json
from dataclasses import asdict

from app.services.diff_parser import ParsedDiff


def original_payload(parsed: ParsedDiff) -> str:
    return json.dumps(asdict(parsed), ensure_ascii=False, separators=(",", ":"))


def model_payload(parsed: ParsedDiff) -> str:
    data = asdict(parsed)
    # Counts are derivable; DOM diff_line is not needed to cite old/new coordinates.
    data.pop("additions")
    data.pop("deletions")
    for file in data["files"]:
        file.pop("additions")
        file.pop("deletions")
        for hunk in file["hunks"]:
            hunk["lines"] = [
                [
                    line["kind"],
                    line["old_line"],
                    line["new_line"],
                    line["content"],
                    line["no_newline"],
                ]
                for line in hunk["lines"]
            ]
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
