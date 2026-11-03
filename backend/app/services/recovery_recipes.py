"""Verify reproducible Sprint 9.1 batch membership using stored evidence only."""

import hashlib
import json
from dataclasses import asdict, replace

from app.review_models import ReviewError
from app.services.audit_batches import setting, subset
from app.services.diff_parser import parse_diff
from app.services.model_payload import model_payload, original_payload
from app.services.output_budget import output_budget


def recovery_limits():
    return {
        "per_batch": setting("INSPECTOR_MAX_RECOVERIES_PER_BATCH", 2, 1, 4),
        "per_review": setting("INSPECTOR_MAX_RECOVERIES_PER_REVIEW", 4, 1, 16),
        "per_action": setting("INSPECTOR_MAX_AUDIT_REQUESTS", 4, 1, 8),
        "batch_bytes": setting("INSPECTOR_BATCH_BYTES", 24000, 4096, 131072),
        "output_budget": output_budget(),
    }


def reconstruct_batches(snapshot):
    def require(condition):
        if not condition:
            raise ReviewError(
                "recovery_unavailable", "Stored batch recipe is not reproducible.", 409
            )

    require(snapshot.audit is not None and snapshot.audit.version == 1)
    require(hashlib.sha256(snapshot.diff.encode()).hexdigest() == snapshot.diff_sha256)
    parsed = parse_diff(snapshot.diff)
    require(json.loads(json.dumps(asdict(parsed))) == snapshot.parsed_diff.model_dump())
    all_hunks = [h.hunk_id for f in parsed.files for h in f.hunks]
    require(len(set(all_hunks)) == len(all_hunks))
    require(
        snapshot.audit.metadata_only_file_ids == [f.file_id for f in parsed.files if not f.hunks]
    )
    groups = {}
    assigned = []
    completed = []
    for batch in snapshot.audit.batches:
        require(batch.batch_id not in groups and bool(batch.hunk_ids))
        require(len(set(batch.hunk_ids)) == len(batch.hunk_ids))
        files = [
            replace(f, hunks=tuple(h for h in f.hunks if h.hunk_id in batch.hunk_ids))
            for f in parsed.files
            if f.file_id in batch.file_ids
        ]
        require([f.file_id for f in files] == batch.file_ids)
        require([h.hunk_id for f in files for h in f.hunks] == batch.hunk_ids)
        require(all(f.hunks for f in files))
        group = subset(files)
        require(len(model_payload(group).encode()) == batch.payload_bytes)
        if batch.payload_sha256 is not None:
            require(
                hashlib.sha256(model_payload(group).encode()).hexdigest() == batch.payload_sha256
            )
        require(len(original_payload(group).encode()) == batch.original_payload_bytes)
        groups[batch.batch_id] = group
        assigned.extend(batch.hunk_ids)
        if batch.status == "completed":
            completed.extend(batch.hunk_ids)
    require(
        bool(groups) and len(set(assigned)) == len(assigned) and set(assigned) == set(all_hunks)
    )
    require(set(completed) == set(snapshot.audit.completed_hunk_ids))
    require(set(all_hunks) - set(completed) == set(snapshot.audit.unanalyzed_hunk_ids))
    if snapshot.analysis:
        require(snapshot.analysis.parsed_diff == snapshot.parsed_diff)
        completed_batches = {b.batch_id for b in snapshot.audit.batches if b.status == "completed"}
        for finding in snapshot.analysis.findings:
            require(bool(finding.batch_ids) and set(finding.batch_ids) <= completed_batches)
    return parsed, groups
