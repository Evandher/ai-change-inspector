# Project rules

- Do not commit or push without explicit user authorization.
- Do not invent APIs, dependencies, or test results. Verify external contracts against official documentation.
- Run the relevant tests after changes, and run available tests, lint and build before delivery. Report actual results and blockers.
- Keep code simple, typed and focused on the approved sprint. Document important decisions in README.md.
- Keep the diff parser pure: standard library only, no FastAPI/Pydantic imports, filesystem, network, subprocesses or mutable global state.
- File and hunk identifiers must be deterministic. Document their stability guarantees.
- Sprint 1 excludes Meta AI integration, authentication and databases.
- Preserve the existing GPL v3 LICENSE.
- Inspect existing files before scaffolding; do not overwrite user changes.
