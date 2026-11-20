#!/bin/bash
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install -q -r backend/requirements.txt
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
