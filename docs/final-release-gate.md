# Final public release gate

Checked November 2, 2026. This gate does not authorize publication, historical rewriting or paid calls.

## Decision

Recommend **B: a new public history from a reviewed, allowlisted source tree**, keeping the existing
checkout/history private. Approval is still required. This avoids carrying internal notes and
agent checkpoint refs into the public source. It does not erase copies already available from the
existing remote. If those copies must be removed, a separate cleanup/access plan is required;
a new history alone is not retroactive erasure.

Before executing: preserve a private full-history archive and notes, verify restore, inventory
contributors/copyright, prepare a separate sanitized directory excluding `.git` and ignored data,
inspect its complete candidate tree, run checks there, then request approval for the initial public
commit and destination. Do not mirror-push this checkout. Preserve attribution explicitly.
Lost public history would include nine development commits, original hashes, blame chronology,
commit messages and author metadata. Keep these privately for provenance; no release tags were
advertised by the remote at this check. No archive/new repository has been created by this gate.

## Git/privacy evidence

A read-only `git ls-remote --heads --tags origin` confirmed live remote `refs/heads/main` at
`cc1ab18952bba73fba5eff3ecd947318c7837582`, matching local main and origin/main.
Current main still contains HANDOFF; its removal exists only in the unstaged working tree.

| Historical file | Commits containing the file |
| --- | --- |
| AGENTS.md | 368dd7d, 97ce48d, e53c1ff |
| HANDOFF.md | f39a985, cc1ab18 |

AGENTS was deleted by 62211ec but remains recoverable in ancestors. Notes expose internal agent
workflow, sprint plans, machine-specific path examples and operational setup/context. No actual
API credential was identified. Historical blob scanning found credential-pattern matches only
in synthetic secret-filter tests, and no tracked `.env`, SQLite or log files. This is heuristic
screening, not proof that every sensitive datum is absent. Do not republish the raw notes.
Local `refs/codex/turn-diffs/*` checkpoint/capture refs also exist, pointing at 23cddf14; they are
private implementation snapshots, not release refs, and are reachable by `--all` scans. Their
names can change during a Codex turn; never mirror or publish them. The remote advertised only
main, not these refs. Remotes may retain unadvertised objects/caches not exposed by ls-remote.

Protect `.env*` except examples, SQLite/WAL/backups, logs, local test/install copies, `.git`,
agent settings, handoffs, internal instructions and user-profile/repository paths. Existing ignore
rules cover runtime files; ignoring does not remove previously committed material. Preserve the
private notes backup separately. Commit authorship metadata also needs the owner's release review.

## Twelve dependency warnings

One underlying advisory, not twelve distinct vulnerabilities:
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
Its published affected range is minimatch <11.0.1; patched version 11.0.1 (registry latest queried:
11.0.4). Exploitation requires attacker-controlled glob patterns and optimizationLevel >=2,
causing CPU/memory amplification. All installed affected nodes are marked development dependencies.
The application does not pass captured diffs to this lint dependency and it is not shipped in the
browser runtime. Malicious lint configuration or a future path using untrusted glob patterns would
still be a relevant developer-tool risk; run lint only on trusted project configuration.

| Package | Installed version(s) | Relationship | Usage | State |
| --- | --- | --- | --- | --- |
| `@eslint-community/eslint-utils` | 4.10.1 | Transitive | Dev / lint | Residual |
| `@eslint/config-array` | 0.21.2 | Transitive | Dev / lint | Residual |
| `@eslint/eslintrc` | 3.3.7 | Transitive | Dev / lint | Residual |
| `@typescript-eslint/eslint-plugin` | 8.72.1 | Transitive | Dev / lint | Residual |
| `@typescript-eslint/parser` | 8.72.1 | Transitive | Dev / lint | Residual |
| `@typescript-eslint/type-utils` | 8.72.1 | Transitive | Dev / lint | Residual |
| `@typescript-eslint/typescript-estree` | 8.72.1 | Transitive | Dev / lint | Residual |
| `@typescript-eslint/utils` | 8.72.1 | Transitive | Dev / lint | Residual |
| `eslint` | 9.39.5 | Direct | Dev / lint | Residual |
| `eslint-plugin-react-refresh` | 0.4.26 | Direct | Dev / lint | Residual |
| `minimatch` | 10.2.6, 3.1.5 | Transitive | Dev / lint | Residual |
| `typescript-eslint` | 8.72.1 | Direct | Dev / lint | Residual |

ESLint 9.39.5, @eslint/config-array and @eslint/eslintrc require minimatch ^3.1.5;
typescript-estree 8.72.1 requires ^10.2.2. A forced minimatch 11 override is outside both major
ranges, and replacing minimatch 3 changes its historical CommonJS/API contract. It is not a clearly
compatible patch. Registry typescript-eslint latest is already the installed 8.72.1. npm marks
some parents fixAvailable=true but offers no complete compatible fix for the graph; this does
not demonstrate a safe release exists for each parent. No dependency/lock changes were justified
or applied. All twelve moderate warnings remain; zero high/critical were reported. Accept them
explicitly as a disclosed development-tool limitation or defer publication until upstream ranges
support a patched version. Do not describe the installation as vulnerability-free.

## Linux / macOS

WSL lists only Docker Desktop (stopped). Attempting its existing Linux shell failed with
`Wsl/Service/CreateInstance/CreateVm/HCS/HCS_E_SERVICE_NOT_AVAILABLE`. No usable Linux runtime
or Ubuntu/Debian distribution was available. No OS features, distributions or tools were installed.
Consequently setup.sh/start.sh, Linux Python/Node/SQLite/wheels, Linux MCP and POSIX safety tests
could not be executed. Windows and Git Bash syntax checks do not count as Linux testing.

macOS is static inspection only: Bash wrappers use script-relative quoted paths and Python3.12,
no PowerShell/CMD dependency; Python paths use pathlib, Windows ctypes imports stay inside the
Windows branch, POSIX untracked reads use no-follow descriptor-relative opens. pywin32 is guarded
by sys_platform == win32. Pinned native wheels (cryptography, pydantic-core, jiter, rpds-py,
Tailwind oxide) still require target-platform/Python/architecture verification. Both Intel and
Apple Silicon remain unverified. Do not claim native compatibility certification.

## Licenses and distribution

The full existing GPLv3 LICENSE is retained unchanged, with GPL-3.0-only package metadata.
No third-party dependency source or environment is added to the public source tree. React,
React DOM and scheduler are included in the frontend build; their verbatim MIT license notices
are now retained in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Include this file with
any distributed frontend build. Backend/dev packages remain separately installed under their own
licenses. Vendored wheels, installers or binary bundles would require a new license/NOTICE and
source-obligation review; this gate approves no such bundle. Do not infer a legal compatibility
guarantee from package metadata. No author copyright identity was invented.

## Release checklist

- [ ] Owner approves Git strategy and treatment of the existing remote's historical copies.
- [ ] Preserve private history and attribution before constructing any new public history.
- [ ] Owner explicitly accepts disclosed lint-tool advisory, or wait for compatible upstream fix.
- [ ] Keep Linux/macOS marked unverified until native checks succeed.
- [ ] Include GPL LICENSE and third-party notices with source/build distribution.
- [ ] Review sanitized allowlisted source, links and metadata; exclude private Git refs/runtime data.
- [ ] Approve staging, commit and publication separately. None is authorized/executed by this gate.

## Final executed checks

Windows: 315 backend tests passed (51.19s), 95 frontend tests passed, Ruff lint/format (49 files),
ESLint, TypeScript/Vite build and pip check passed. Git Bash syntax checks and internal Markdown
links passed. The active SQLite table digests before/after match exactly and integrity_check is ok.
No actual backend key or known private machine/review identifiers were found in candidate public
files. No provider calls, audit/recovery tool calls, Cotiza modifications, staging, commits, pushes,
fetches or history rewrites occurred. Read-only remote reference discovery was used.

Files changed by this final gate only: README.md, CONTRIBUTING.md, docs/release-validation.md;
created docs/final-release-gate.md and THIRD_PARTY_NOTICES.md. Previously prepared working-tree
changes remain intact. Dependency manifests/lockfiles were not changed by this gate. The local
tracker did not respond; no tasks were created or updated and its service was not restarted.
