#!/bin/bash
set -u

URL="http://127.0.0.1:8000"
BROWSER="$(command -v chromium || command -v chromium-browser || true)"

if [ -z "$BROWSER" ]; then
  echo "Chromium wurde nicht gefunden" >&2
  exit 1
fi

for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 2 "$URL/api/health" >/dev/null; then
    break
  fi
  sleep 1
done

FLAGS=(
  --kiosk
  --noerrdialogs
  --disable-infobars
  --disable-session-crashed-bubble
  --disable-translate
  --disable-features=TranslateUI
  --disable-dev-shm-usage
  --disable-gpu
  --disable-gpu-compositing
  --disable-pinch
  --overscroll-history-navigation=0
  --touch-events=enabled
)

while true; do
  "$BROWSER" "${FLAGS[@]}" "$URL"
  echo "Chromium wurde beendet; Neustart in 3 Sekunden" >&2
  sleep 3
done
