# Installation

## Requirements

Use Python **3.12.x** for the pinned dependency set, Node.js **24.x (recommended) or 22.x â‰¥22.12**, npm 9+, and Git.
Confirm `python --version` is 3.12 on Windows (or use `py -3.12` if registered).
The frontend engine follows Vitest: v22 ≥22.12, v24, or v26+; odd v23/v25 are excluded.
Node 24.14.0 and Python 3.12.10 were exercised on this laptop.
Only Python 3.12 is currently validated; newer Python versions are not claimed compatible.
Install these with your OS/package manager; scripts do not install global tools or request admin.
Ubuntu/Debian also need the matching `python3.12-venv` package when venv is packaged separately.
On macOS use a Python 3.12 distribution appropriate to Intel or Apple Silicon; native wheels
for pinned packages must be available, otherwise installation may require build tools.

## Automated setup

Windows: `powershell -File scripts/setup.ps1` (or `./scripts/setup.ps1` in PowerShell).
If your policy blocks local scripts, use the manual commands below; do not change global policy.
Linux/macOS: `bash scripts/setup.sh`. No executable bit is required.
Scripts resolve the checkout from their own location and work from another working directory.
They verify tool versions, create `backend/.venv`, install the exact Python lock and use `npm ci`.
They copy `.env.example` only if `.env` does not exist. They never initialize/reset SQLite,
start an audit, install MCP, or overwrite credentials. Re-running setup reinstalls dependencies;
it must not run concurrently with a frontend build or dependency update.

The lock was originally resolved on Windows. `pywin32` is explicitly Windows-only; other
native packages still require target-platform wheels/build support. Linux/macOS remain unverified.

## Manual Windows installation

From the checkout root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
npm.cmd --prefix frontend ci
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

## Manual Linux/macOS installation

From the checkout root:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
npm --prefix frontend ci
if [ ! -e backend/.env ]; then cp backend/.env.example backend/.env; fi
```

## Configuration and credentials

Edit the ignored `backend/.env`. Obtain your own API key through the
[Meta developer platform](https://dev.meta.ai/); account access and model availability are external
prerequisites. Set `MODEL_API_KEY` only on the backend. Never use a `VITE_*` secret, paste a key
into an agent prompt, or commit `.env`. The SDK package is named `openai`, but the fixed provider
is `https://api.meta.ai/v1` and fixed model is `muse-spark-1.3`; there is no model-selection variable.

Authorize actual Git roots with absolute paths. API and MCP must use identical IDs and roots.
These are examples to replace, not roots automatically created by setup:

```dotenv
# Windows; forward slashes avoid JSON backslash escaping
INSPECTOR_REPOSITORIES={"project":"C:/work/project"}
# Linux: {"project":"/home/developer/work/project"}
# macOS: {"project":"/Users/developer/work/project"}
```

Default SQLite is `backend/.local/reviews.sqlite3`, independent of the terminal working directory.
Optional `INSPECTOR_DB_PATH` must be absolute; the application creates the parent directory.
SQLite is private runtime data. Use SQLite's backup API for a consistent backup before upgrades;
do not simply copy an open WAL database. Migrations are additive, never a historical-data reset.
Keep a backup and verify existing reviews after upgrading. One API worker/process per database.

| Variable | Default | Range / purpose |
| --- | --- | --- |
| `INSPECTOR_API_URL` | `http://127.0.0.1:8000` | Local API URL |
| `INSPECTOR_WEB_URL` | `http://127.0.0.1:5173` | Exact local browser origin |
| `INSPECTOR_MAX_AUDIT_REQUESTS` | 4 | 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“8 initial calls / one recovery action |
| `INSPECTOR_BATCH_BYTES` | 24000 | 4096ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“131072 UTF-8 evidence bytes |
| `INSPECTOR_MAX_OUTPUT_TOKENS` | 8192 | 16 through configured ceiling |
| `INSPECTOR_OUTPUT_TOKEN_CEILING` | 8192 | 16ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“8192; 12288 unsupported |
| `INSPECTOR_MAX_RECOVERIES_PER_BATCH` | 2 | 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“4 additional reservations |
| `INSPECTOR_MAX_RECOVERIES_PER_REVIEW` | 4 | 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“16 additional reservations |

Start helper supports literal `127.0.0.1` HTTP URLs and uses their ports. Set both URLs consistently
when changing ports; configure MCP `--api-url` too. Shell-exported values override `.env`.
Do not change limits as an automatic response to a failure.

## Running

Windows: `./scripts/start.ps1`. Linux/macOS: `bash scripts/start.sh`.
Leave the terminal open. Ctrl+C stops only the two processes it started. An occupied port is an
error, never an invitation to kill another service. Start checks ports first; a subsequent race
still makes the server fail rather than replace another instance.

Manual API (Windows, from `backend`):

```powershell
.venv/Scripts/python.exe -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --workers 1
```

Linux/macOS, from `backend`, replace the executable with `.venv/bin/python`.
In another terminal, from `frontend`: `npm.cmd run dev` on Windows, `npm run dev` on POSIX.
These manual commands use the default ports; custom ports also require matching proxy and origin
configuration. The combined start helper passes the API URL to the Vite proxy automatically.
Do not use reload or multiple workers against the same review database.

Build the frontend with `npm run build` (`npm.cmd` on Windows). The current documented runtime
is local Vite plus FastAPI; a production hosting deployment is outside the supported setup.

## Troubleshooting

Missing tool: install it, reopen the terminal and rerun setup. Missing key: local parsing still works;
model analysis does not. Blocked repository: compare the absolute root and ID in API and MCP.
Missing wheels on Linux/macOS: report the exact platform/package; do not silently unpin dependencies.
Timeout: consult the existing review before requesting another paid action.
