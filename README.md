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

## Raspberry Pi Pico WH / BLE-HID

Der Pico WH verbindet sich per **MicroPython** als Bluetooth-Tastatur mit dem PC. Der Raspberry Pi sendet Makros über UART:

- Pico `GP0 / TX` → Raspberry-Pi `GPIO15 / RX`, Pin 10
- Pico `GP1 / RX` → Raspberry-Pi `GPIO14 / TX`, Pin 8
- Gemeinsame Masse an Pin 6, 9, 14, 20, 25, 30, 34, 39
- UART: 115200 Baud
- Optional LED-Strip (WS2812/SK6812): `DIN` an Pico `GP2`, gemeinsame Masse, 5V an `VSYS`

Firmware liegt unter `firmware/pico/code.py` und benötigt auf dem Pico WH keine externen Python-Pakete. Die Makros werden auf der Config-Seite unter `http://<PI-IP>:8000/config` bearbeitet. Die Makro-Seite auf dem Pi sendet die ausgewählten Aktionen über UART an den Pico.

Setup kurz:
1. Aktuelle MicroPython-`uf2` für Pico W/WH flashen.
2. `firmware/pico/code.py` als `main.py` auf den Pico kopieren.
3. Am PC Bluetooth-Gerät `DeskBuddy` koppeln.
4. Danach sendet der Pi Shortcuts/Text per UART (115200).

In den Pico-Macros gibt es zusätzlich den Typ **LED**. Eingaben:
- `#RRGGBB` (z. B. `#3ecf8e`) setzt alle 8 LEDs auf diese Farbe.
- `off` schaltet den Strip aus.

Vor dem Einsatz: Raspberry-Pi UART-Konsole deaktivieren und Serial-Zugriff erlauben. Keine Spannungen von 5 V auf die Pico-GPIOs legen.

## iCloud-Kalender

Erstelle in den Apple-ID-Einstellungen ein app-spezifisches Passwort. Dieses sowie die Apple-ID können unter **Optionen → iCloud-Kalender** eingetragen werden. Anschließend werden alle verfügbaren iCloud-Kalender geladen und mehrere Kalender können über Kontrollkästchen zur Anzeige ausgewählt werden.
Alternativ können `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD` und `ICLOUD_CALDAV_URL` in `backend/.env` gesetzt werden. Zugangsdaten werden nicht an das Frontend ausgegeben.

## Notion

`backend/.env` aus `backend/.env.example` erstellen und freigegebene Datenbank-IDs eintragen. API-Token und Datenbank-IDs bleiben ausschließlich im Backend.

## Raspberry Pi

`./scripts/install.sh` vorbereitet apt-Abhängigkeiten und einen Desktop-Autostart. Danach werden FastAPI und Chromium über `scripts/start-and-kiosk.sh` gestartet.
