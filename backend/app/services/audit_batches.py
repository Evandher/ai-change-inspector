"""Bounded sequential calls over one immutable snapshot; never recaptures or retries."""

import hashlib
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace

from app.provider_models import AuditBatch, AuditRun
from app.services.diff_parser import ParsedDiff
from app.services.model_client import MAX_ANALYSIS_BYTES
from app.services.model_payload import model_payload, original_payload

_progress = ContextVar("audit_progress", default=None)


@contextmanager
def audit_progress(callback):
    token = _progress.set(callback)
    try:
        yield
    finally:
        _progress.reset(token)


def report_progress(audit, analysis):
    callback = _progress.get()
    if callback:
        callback(audit, analysis)


def setting(name, default, minimum, maximum):
    value = os.environ.get(name, str(default))
    try:
        number = int(value)
    except ValueError:
        number = 0
    if not minimum <= number <= maximum:
        from app.services.model_client import AnalysisError

        raise AnalysisError("invalid_audit_config", "Invalid bounded audit configuration.", 503)
    return number


def subset(files):
    merged = {}
    for file in files:
        if file.file_id in merged:
            merged[file.file_id] = replace(file, hunks=(*merged[file.file_id].hunks, *file.hunks))
        else:
            merged[file.file_id] = file
    files = tuple(merged.values())
    return ParsedDiff(
        tuple(files),
        sum(line.kind == "addition" for f in files for h in f.hunks for line in h.lines),
        sum(line.kind == "deletion" for f in files for h in f.hunks for line in h.lines),
    )


def plan_batches(parsed):
    limit = setting("INSPECTOR_MAX_AUDIT_REQUESTS", 4, 1, 8)
    budget = setting("INSPECTOR_BATCH_BYTES", 24000, 4096, MAX_ANALYSIS_BYTES)
    units = []
    metadata = []
    for file in parsed.files:
        if not file.hunks:
            metadata.append(file.file_id)
            continue
        if len(model_payload(subset([file])).encode()) <= budget:
            units.append(file)
        else:
            # Never split a hunk or regenerate its identity / coordinates.
            units.extend(replace(file, hunks=(hunk,)) for hunk in file.hunks)
    groups = []
    current = []
    for unit in units:
        if current and len(model_payload(subset([*current, unit])).encode()) > budget:
            groups.append(subset(current))
            current = []
        current.append(unit)
    if current:
        groups.append(subset(current))
    audit = AuditRun(
        max_requests=limit,
        metadata_only_file_ids=metadata,
        unanalyzed_hunk_ids=[h.hunk_id for f in parsed.files for h in f.hunks],
    )
    for index, group in enumerate(groups):
        size = len(model_payload(group).encode())
        batch = AuditBatch(
            batch_id=f"batch-{index + 1}",
            file_ids=list(dict.fromkeys(f.file_id for f in group.files)),
            hunk_ids=[h.hunk_id for f in group.files for h in f.hunks],
            payload_bytes=size,
            payload_sha256=hashlib.sha256(model_payload(group).encode()).hexdigest(),
            payload_version=1,
            original_payload_bytes=len(original_payload(group).encode()),
        )
        if size > budget:
            batch.status, batch.error_code = "failed", "hunk_too_large"
        audit.batches.append(batch)
    return audit, groups
