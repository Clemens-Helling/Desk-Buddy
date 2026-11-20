# Deskbuddy

Chromium-Kiosk-Frontend für ein Raspberry-Pi-7-Zoll-Display (primär 800 × 480) mit React/Vite und FastAPI-Backend.

## Lokal starten

1. Frontend bauen: `cd frontend && npm install && npm run build`
2. Python-Abhängigkeiten: `python -m pip install -r backend/requirements.txt`
3. Backend: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
4. Lokal öffnen: `http://127.0.0.1:8000`
5. Vom iPad im selben WLAN öffnen: `http://<PC-IP-Adresse>:8000`

Für die Vite-Entwicklungsansicht zusätzlich `cd frontend && npm run dev`; erreichbar unter `http://<PC-IP-Adresse>:5173`. Die `/api`-Anfragen werden dabei an Port 8000 weitergeleitet.

## Notion

`backend/.env` aus `backend/.env.example` erstellen und freigegebene Datenbank-IDs eintragen. API-Token und Datenbank-IDs bleiben ausschließlich im Backend.

## Raspberry Pi

`./scripts/install.sh` vorbereitet apt-Abhängigkeiten und einen Desktop-Autostart. Danach werden FastAPI und Chromium über `scripts/start-and-kiosk.sh` gestartet.
