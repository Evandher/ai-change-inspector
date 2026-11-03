"""Offline reproducible payload sizes. Reads diff files only; never calls Git or Meta."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.audit_batches import plan_batches
from app.services.diff_parser import parse_diff
from app.services.model_payload import model_payload, original_payload


def measure(text):
    parsed = parse_diff(text)
    audit, _ = plan_batches(parsed)
    before = len(original_payload(parsed).encode())
    after = len(model_payload(parsed).encode())
    return {
        "original_bytes": before,
        "compact_bytes": after,
        "reduction_percent": round(100 * (before - after) / before, 2),
        "planned_batches": len(audit.batches),
        "max_requests": audit.max_requests,
        "batch_bytes": [b.payload_bytes for b in audit.batches],
        "total_planned_payload_bytes": sum(b.payload_bytes for b in audit.batches),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diff", nargs="+", type=Path)
    for path in parser.parse_args().diff:
        print(json.dumps({"fixture": path.name, **measure(path.read_text(encoding="utf-8"))}))
