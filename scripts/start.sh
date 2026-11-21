#!/bin/bash
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate

REQ_HASH="$(sha256sum backend/requirements.txt | cut -d' ' -f1)"
REQ_MARKER=".venv/.requirements-hash"
if [ ! -f "$REQ_MARKER" ] || [ "$(cat "$REQ_MARKER")" != "$REQ_HASH" ]; then
  python -m pip install --disable-pip-version-check -q -r backend/requirements.txt
  printf '%s' "$REQ_HASH" > "$REQ_MARKER"
fi

if [ ! -f "frontend/dist/index.html" ] && [ -f "frontend/package.json" ] && command -v npm >/dev/null; then
  cd frontend
  npm run build
  cd ..
fi

exec python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 15 --log-level warning
