#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
./scripts/start.sh > /tmp/deskbuddy.log 2>&1 &
./scripts/kiosk.sh
