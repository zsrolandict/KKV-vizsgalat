#!/usr/bin/env bash
set -euo pipefail
KKV_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KKV_PROJECT_DIR"
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' 'Előbb futtassa: bash scripts/install.sh' >&2
  exit 1
fi
exec .venv/bin/python -m uvicorn app.main:app --host "${KKV_HOST:-127.0.0.1}" --port "${KKV_PORT:-8000}"
