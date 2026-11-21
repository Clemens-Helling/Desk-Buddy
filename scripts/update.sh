#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

log() {
  printf '\n==> %s\n' "$*"
}

log "Stoppe laufende Deskbuddy-Prozesse"
pkill -f '/scripts/kiosk.sh' 2>/dev/null || true
pkill -f 'chromium' 2>/dev/null || true
pkill -f 'uvicorn backend.main:app' 2>/dev/null || true
sleep 2

log "Sichere lokale Änderungen"
if [ -n "$(git status --porcelain)" ]; then
  git stash push -u -m "Deskbuddy update $(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
fi

log "Aktualisiere Repository"
git fetch origin main
git pull --ff-only origin main

log "Installiere Abhängigkeiten"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install --disable-pip-version-check -q -r backend/requirements.txt

log "Baue Frontend"
cd frontend
if [ -f package-lock.json ]; then
  npm ci --silent
else
  npm install --silent
fi
npm run build
cd "$DIR"

chmod +x scripts/*.sh

log "Starte Backend und Frontend"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if command -v setsid >/dev/null; then
  setsid -f env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    ./scripts/start-and-kiosk.sh >/tmp/deskbuddy-update.log 2>&1 </dev/null
else
  nohup env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    ./scripts/start-and-kiosk.sh >/tmp/deskbuddy-update.log 2>&1 </dev/null &
fi

for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8000/api/health >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl --fail --silent --max-time 2 http://127.0.0.1:8000/api/health >/dev/null; then
  echo "Fehler: Backend wurde nicht erreichbar." >&2
  tail -n 30 /tmp/deskbuddy.log 2>/dev/null || true
  exit 1
fi

log "Update abgeschlossen"
log "Frontend-Log: /tmp/deskbuddy-update.log"
log "Backend-Log: /tmp/deskbuddy.log"
IP="$(hostname -I | awk '{print $1}')"
log "Konfiguration: http://${IP}:8000/config"
