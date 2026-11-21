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

log "Sichere lokale Änderungen an Startskripten"
STASH_NAME="Deskbuddy update $(date '+%Y-%m-%d %H:%M:%S')"
LOCAL_SCRIPTS=(scripts/install.sh scripts/kiosk.sh scripts/start.sh scripts/start-and-kiosk.sh)
if git status --porcelain -- "${LOCAL_SCRIPTS[@]}" | grep -q .; then
  git stash push -m "$STASH_NAME" -- "${LOCAL_SCRIPTS[@]}"
fi

log "Aktualisiere Repository"
git fetch origin main
git pull --ff-only origin main

log "Installiere Abhängigkeiten"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install --disable-pip-version-check -q -r backend/requirements.txt

cd frontend
if [ -f package-lock.json ]; then
  npm ci --silent
else
  npm install --silent
fi
npm run build
cd "$DIR"

chmod +x scripts/*.sh

log "Starte Deskbuddy"
export DISPLAY="${DISPLAY:-:0}"
if [ -z "${XAUTHORITY:-}" ]; then
  if [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
  fi
fi
KIOSK_ENV=(env DISPLAY="$DISPLAY")
if [ -n "${XAUTHORITY:-}" ]; then
  KIOSK_ENV+=(XAUTHORITY="$XAUTHORITY")
fi
nohup "${KIOSK_ENV[@]}" ./scripts/start-and-kiosk.sh >/tmp/deskbuddy-update.log 2>&1 </dev/null &

log "Update abgeschlossen"
log "Log: /tmp/deskbuddy-update.log"
log "Konfiguration: http://$(hostname -I | awk '{print $1}'):8000/config"
