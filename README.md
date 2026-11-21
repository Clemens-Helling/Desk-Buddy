# Deskbuddy

Chromium-Kiosk-Frontend für ein Raspberry-Pi-7-Zoll-Display (primär 800 × 480) mit React/Vite und FastAPI-Backend.

## Raspberry-Pi-Update

Für spätere Updates reicht auf dem Raspberry Pi:

```bash
cd ~/Desk-Buddy
./scripts/update.sh
```

Das Script beendet laufende Prozesse, sichert lokale Änderungen an Startskripten, zieht den aktuellen Stand, installiert Abhängigkeiten, baut das Frontend und startet Deskbuddy neu.

## Lokal starten

1. Frontend bauen: `cd frontend && npm install && npm run build`
2. Python-Abhängigkeiten: `python -m pip install -r backend/requirements.txt`
3. Backend: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
4. Lokal öffnen: `http://127.0.0.1:8000`
5. Vom iPad im selben WLAN öffnen: `http://<PC-IP-Adresse>:8000`

Für die Vite-Entwicklungsansicht zusätzlich `cd frontend && npm run dev`; erreichbar unter `http://<PC-IP-Adresse>:5173`. Die `/api`-Anfragen werden dabei an Port 8000 weitergeleitet.

## KI-Avatar

Optional kann der Serverereignisse an Gemini senden:

```env
GEMINI_API_KEY=dein_key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Ohne Key oder bei API-/Offline-Fehlern verwendet der Desk Buddy lokale Nachrichten. Der Avatar wird nur durch eigene Events aktualisiert, nicht per Polling.

## Nachtmodus

Unter **Optionen** kann der Nachtmodus eingeschaltet und eine freie Ausschalt- sowie Aufwachzeit festgelegt werden. Während der Schlafzeit wird die Raspberry-Pi-Hintergrundbeleuchtung auf null gesetzt. Ein Fingertipp aktiviert die zuvor gespeicherte Helligkeit wieder.

## Fernkonfiguration

Die Einstellungen werden nicht auf dem Raspberry-Pi-Bildschirm angezeigt. Von einem PC oder Smartphone kann die Konfigurationsseite im selben WLAN geöffnet werden:

`http://<RASPBERRY-PI-IP>:8000/config`

Die IP-Adresse des Pis ermittelt man mit `hostname -I`.

## iCloud-Kalender

Erstelle in den Apple-ID-Einstellungen ein app-spezifisches Passwort. Dieses sowie die Apple-ID können unter **Optionen → iCloud-Kalender** eingetragen werden. Anschließend werden alle verfügbaren iCloud-Kalender geladen und mehrere Kalender können über Kontrollkästchen zur Anzeige ausgewählt werden.
Alternativ können `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD` und `ICLOUD_CALDAV_URL` in `backend/.env` gesetzt werden. Zugangsdaten werden nicht an das Frontend ausgegeben.

## Notion

`backend/.env` aus `backend/.env.example` erstellen und freigegebene Datenbank-IDs eintragen. API-Token und Datenbank-IDs bleiben ausschließlich im Backend.

## Raspberry Pi

`./scripts/install.sh` vorbereitet apt-Abhängigkeiten und einen Desktop-Autostart. Danach werden FastAPI und Chromium über `scripts/start-and-kiosk.sh` gestartet.
