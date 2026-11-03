# Contributing

Use Python 3.12 and Node.js 24.x or 22.x â‰¥22.12. Follow [installation](docs/installation.md).
Keep changes focused and preserve canonical file/hunk/reference IDs, immutable snapshots, human
feedback and repository authorization. Do not execute audited material or model-suggested tests.
Do not add automatic paid calls/retries. Use mocks and temporary databases; never test against
an operator's actual SQLite file or private repository. Keep EN/ES and existing visual identity.

From `backend` (Windows; on POSIX use `.venv/bin/python`):

```powershell
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check app tests scripts run_mcp.py ../scripts/manage.py
.venv/Scripts/python.exe -m ruff format --check app tests scripts run_mcp.py ../scripts/manage.py
.venv/Scripts/python.exe -m pip check
```

From `frontend` (`npm.cmd` on Windows):

```bash
npm test -- --run
npm run lint
npm run build
```

Tests use mocked provider responses and temporary repositories; no real Meta calls are required.
Document actual platforms tested. Do not claim macOS/Linux compatibility from static inspection alone.
Do not commit keys, `.env`, SQLite/backups, logs, generated output or internal agent/handoff notes.

Project code is GPL-3.0-only; retain the existing LICENSE. Python/npm dependencies have their own
licenses. Review their metadata and license files, including native/transitive packages, when
redistributing bundles. Dependency installation is not a grant to relicense third-party code.

Third-party frontend attribution: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
