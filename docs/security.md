# Security and limitations

## Intended use

Local, single-user development only. Bind API and Vite to `127.0.0.1`, one API worker per SQLite
file. No authentication, multiuser isolation or public-hosting claim. Host/Origin/loopback checks,
JSON requirements and request markers reduce browser-origin attacks; another local process can
forge these headers. Human confirmation is a workflow boundary, not cryptographic identity.
Agent provenance is declared and unauthenticated.

## Evidence capture

Only operator-authorized IDs and absolute Git roots are accepted. Use a regular working repository
with a local `.git` directory; linked worktrees, bare repositories and external object stores are
not supported. Local Git includes/clean filters/fsmonitor/promisor configuration is rejected. Git capture uses bounded commands
without shell execution, external diff helpers or audited project code/tests. Staged and unstaged
are separate scopes. Untracked capture is opt-in, bounded text only, never stages or follows links.
Windows uses locked handles and rejects reparse points; POSIX uses descriptor-relative no-follow
opens and before/after metadata checks. Unsupported safe traversal fails closed. Hardlinks,
unsafe paths, sensitive candidates, unsupported/binary/oversized files are excluded or blocked.
Filesystem/Git state is not a fully atomic snapshot; hostile privileged mutation is outside scope.

HTTP bodies are bounded at 8 MiB; parser/capture have additional bounds. The independent parser and
validator preserve deterministic references, original diff/hash and immutable snapshots. Findings
and suggested tests are untrusted text and are never executed. Evidence validity is not correctness.

## Provider and cost

Explicit model actions send source changes to Meta and may consume credits. Source can be private
or legally restricted: inspect it and obtain permission before submission. Sensitive-path/content
filters and export redaction are heuristic, not guaranteed secret detection. Never commit `.env`,
keys, databases, backups or private screenshots. Never put credentials in frontend environment.

Requests are bounded, sequential, `store=false`, without tools/history and SDK retries. Initial
audit default is four distinct calls (maximum eight). Recovery adds only explicitly confirmed
eligible batches within action/per-batch/per-review limits. Reserved attempts consume allowances
conservatively even if interrupted. A client timeout does not prove a request stopped; inspect
its recorded review before another paid action. No automatic recovery or free-text output fallback.
Diagnostics allowlist metadata; prompts, partial provider bodies and credentials are not persisted.

## Release audit

Internal `AGENTS.md` is ignored and absent from the current tracked tree, but exists in historical
commits. `HANDOFF.md` is removed from the working tree after a private backup; it also exists in
history. Ignoring/removing these files does not erase prior commits. Review historical contents
and remote reachability before publishing. No history rewriting is part of this preparation.
Dependency license metadata is a screening aid, not legal advice or a complete transitive notice
bundle. Distributors must retain relevant third-party notices and review the actual distribution.
