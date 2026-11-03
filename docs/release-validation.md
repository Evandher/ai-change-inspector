# Release validation

Validation performed on the available Windows laptop, November 2, 2026. No paid provider request,
real audit, recovery or change to an audited repository was made.

| Check | Result |
| --- | --- |
| Python backend suite | 315 tests passed, using mocks and temporary data |
| Frontend suite | 95 tests passed |
| Ruff lint and format | Passed |
| ESLint / TypeScript / Vite build | Passed |
| Python dependency consistency | `pip check` passed |
| Clean isolated Windows setup | New venv and exact dependencies installed; `npm ci` succeeded |
| Spaces and Unicode | Setup, API, proxy, frontend and stdio MCP ran in such a checkout path |
| Setup re-run | Existing `.env` and SQLite byte hashes unchanged |
| Occupied port / shutdown | Refused the active API port; temporary process groups closed |
| Alternate ports | API 8012, frontend 5185 and proxied health returned HTTP 200 |
| Bash wrappers | Syntax checked with Git Bash; no native Linux/macOS execution |
| WSL | Only Docker Desktop distribution present; not counted as Ubuntu/Debian validation |
| Offline browser | Included synthetic example parsed successfully; screenshot contains no private review |
| MCP | Real stdio handshake and both tools discovered; zero tool invocations |

Tests cover UTF-8, CRLF/LF, Git capture and security filters in temporary repositories. Native
POSIX no-follow traversal and platform-specific dependency wheels still need execution on Linux
and macOS. This release does not claim those platforms are verified.

## Dependency and license screening

The existing full GPLv3 license remains unchanged, with GPL-3.0-only package metadata. Python
installed-package license metadata and npm lock license identifiers were inspected; all installed
Python distributions provided license metadata/classifiers. npm identifiers included MIT, ISC,
Apache-2.0, BSD variants, MPL-2.0, Python-2.0, BlueOak-1.0.0 and CC-BY-4.0. No dependency is
relicensed by this project. A final distribution/notice review is still required; metadata screening
is not a legal compatibility opinion or a vendored third-party notice bundle.

`npm audit` reported **12 moderate, zero high/critical** dependency vulnerabilities, in the
ESLint/typescript-eslint/minimatch development-tool chain. The underlying reported advisory is
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
The audit did not offer a complete automatic fix for the existing graph. No `audit fix`, forced
upgrade or unrelated dependency migration was applied. Resolve or explicitly assess this issue
before public release. The install also warned about deprecated ESLint and whatwg-encoding.

## Current tree and historical notes

Initial working tree was clean. `AGENTS.md` was already ignored/untracked. `HANDOFF.md` was tracked;
a verified private copy was made outside the checkout and the public working-tree copy removed.
Its deletion remains unstaged. No commit, push, fetch, rewrite or Git configuration change occurred.

`AGENTS.md` existed in commits `368dd7d`, `97ce48d`, `e53c1ff` and was removed in `62211ec`.
`HANDOFF.md` appears in `f39a985` and `cc1ab18`. These commits are reachable from the locally cached
`origin/main`; this is evidence of the last known remote state, not a fresh remote verification.
Historical notes contain internal workflow instructions and the handoff includes machine/review
context. Removing them today does not remove them from history.

All reachable historical blob objects were screened with bounded credential-pattern checks.
The only potential matches were synthetic secret-filter test fixtures; no real credential was
identified by this scan. This is heuristic screening, not a guarantee of absence. No credential
values are reproduced in the report. Private `.env`, SQLite, backups and runtime/test files remain
ignored. Before publication, decide whether internal historical notes are acceptable or authorize
a separate history-cleanup plan. No destructive history operation was performed.

## Files in this preparation

Created: `.gitattributes`, `CONTRIBUTING.md`, `scripts/manage.py`, `scripts/ruff.toml`,
`scripts/setup.ps1`, `scripts/setup.sh`, `scripts/start.ps1`, `scripts/start.sh`,
`backend/tests/test_distribution.py`, `docs/installation.md`, `docs/architecture.md`,
`docs/security.md`, `docs/mcp.md`, `docs/demo.md`, `docs/release-validation.md`, and
`docs/images/local-diff-example.jpg`.

Updated: `README.md`, `.gitignore`, `backend/.env.example`, `backend/requirements-lock.txt`,
`frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`.

Removed from working tree after verified private backup: `HANDOFF.md`.
Unchanged: `LICENSE`, parser/validator, MCP contracts, audit/recovery business logic,
agent Skill safety workflow, private environment and real SQLite contents.

## Final gate follow-up

See [Final public release gate](final-release-gate.md) for fresh remote verification, per-package
residual dependency warnings, WSL failure evidence and the proposed clean-history publication plan.
The original cached-remote statement above records the earlier check; the follow-up supersedes it.
