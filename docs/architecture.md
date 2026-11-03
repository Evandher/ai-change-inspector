# Architecture

React/TypeScript/Vite renders snapshots and human feedback. FastAPI orchestrates validation,
model requests and SQLite persistence. The stdio MCP server captures an explicitly authorized
Git scope and registers it with the local API. The Skill coordinates the developer workflow.

The deterministic parser assigns file/hunk IDs and old/new line coordinates. Independent reference
validation checks model citations against this parse, not against a later checkout. Invalid
references stay visible and never receive invented navigation targets. A valid reference is
structural evidence, not proof of behavior.

Original diffs, results and terminal snapshots are immutable. Human decisions/comments are stored
separately. Parent–child relationships support comparison, not automatic resolution tracking.
Exports read existing results without regenerating them. Historical absent metadata stays unknown.

## Large audits and selective recovery

A captured diff is stored once. Whole files are grouped within a byte budget; oversized files split
only along original hunk boundaries. Oversized indivisible hunks are not sent. Canonical IDs,
line coordinates and context are retained. A compact lossless evidence representation removes
repeated per-line keys, not source lines. Measure locally with:

```bash
backend/.venv/bin/python backend/scripts/measure_audit_payload.py examples/diffs/modified.diff examples/diffs/multiple-files.diff
```

On Windows use `backend/.venv/Scripts/python.exe`. Payload bytes are not token/cost estimates.
Batches do not share reasoning; cross-file/cross-hunk risks can be missed. A global audit is
completed only when all required batches complete. Partial audits retain valid hypotheses from
completed batches and clearly expose unanalyzed coverage. Diagnostics preserve reported status,
reason, correlation IDs and token counts; absent values are not inferred. Partial output is never
accepted as findings. The provider timeout is 60 seconds per transport call, with zero SDK retries.

Only failed/incomplete reproducible batches are eligible for selective recovery, with explicit
human confirmation in Review Detail. Completed batches are never rerun. Recovery validates the
stored diff hash, parse, memberships and payload against the original snapshot; it never recaptures
Git. `review_recovery_runs` and `review_batch_attempts` preserve append-only terminal histories,
quotas, idempotency and one active recovery per review. Original result rows remain unchanged;
read projections append completed recovery findings without changing old feedback indexes.
A restart marks abandoned attempts interrupted without resuming paid work. This is a single-process
local design, not distributed worker coordination. No recovery MCP tool is provided.
