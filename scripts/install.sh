#!/usr/bin/env bash
set -euo pipefail
KKV_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KKV_PROJECT_DIR"
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 vagy újabb szükséges."'
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --system-site-packages .venv
fi
.venv/bin/python -m pip install --quiet --no-cache-dir --disable-pip-version-check -r requirements.txt
.venv/bin/python -m unittest discover -s tests -t . -q
if ! command -v soffice >/dev/null 2>&1; then
  printf '%s\n' 'A Word-export elérhető. A PDF-exporthoz telepítse a LibreOffice-ot (soffice).' >&2
fi
