#!/bin/bash
set -e
sudo apt update
sudo apt install -y python3-venv python3-pip chromium-browser unclutter
mkdir -p "$HOME/.config/autostart"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cat > "$HOME/.config/autostart/deskbuddy.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deskbuddy
Exec=$PROJECT_DIR/scripts/start-and-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$PROJECT_DIR"/scripts/*.sh
