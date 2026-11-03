#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Install Python 3.12 (with venv support) and reopen your terminal." >&2
  exit 1
fi
exec python3.12 "$script_dir/manage.py" start
