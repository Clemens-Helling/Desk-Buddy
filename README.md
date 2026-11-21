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

Der Pico W/WH meldet sich per **MicroPython** über Bluetooth LE als HID-Gerät (Tastatur + Medientasten) am PC an. Der Raspberry Pi 4 mit dem Desk-Buddy sendet die Makros über UART an den Pico, der Pico steuert zusätzlich den LED-Streifen:

- Pico `GP0 / TX` → Raspberry-Pi `GPIO15 / RX`, Pin 10
- Pico `GP1 / RX` → Raspberry-Pi `GPIO14 / TX`, Pin 8
- Gemeinsame Masse (z. B. Pi Pin 6 ↔ Pico GND)
- UART: 115200 Baud, eine JSON-Zeile pro Befehl, Antwort `ok ...` oder `error <grund>`
- LED-Strip (WS2812/SK6812): `DIN` an Pico `GP2`, gemeinsame Masse, 5 V an `VSYS`
- Die Stromversorgung des Pico kommt vom Pi (z. B. Pi 5 V → Pico `VSYS`) oder über dessen USB-Anschluss.

Setup:
1. Aktuelle MicroPython-`uf2` für Pico W/WH flashen (mindestens 1.21 wegen Pairing/Bonding).
2. `firmware/pico/code.py` als `main.py` auf den Pico kopieren.
3. Am PC in den Bluetooth-Einstellungen das Gerät `DeskBuddy` hinzufügen (es erscheint als Tastatur).
4. Auf dem Pi die UART-Login-Konsole deaktivieren und die serielle Schnittstelle aktivieren (`raspi-config` → Interface Options → Serial Port: Login-Shell **nein**, Hardware **ja**).

Die Kopplung wird auf dem Pico in `ble_keys.json` gespeichert, sodass der PC ihn nach einem Neustart automatisch wieder verbindet. Wenn der PC den Pico nicht mehr verbindet (z. B. nach dem Löschen des Geräts am PC): Gerät am PC entfernen, vom Pi aus `{"type": "unpair"}` an den Pico senden (oder `ble_keys.json` löschen) und neu koppeln.

Unterstützte Makros: Shortcuts (z. B. `CTRL`+`C`, `F13`–`F24`), Medientasten (`VOLUME_UP`, `VOLUME_DOWN`, `MUTE`, `PLAY_PAUSE`, `NEXT`, `PREV`, ...), Text (US-Tastaturlayout, Umlaute werden übersprungen) und LED-Steuerung. Ein Befehl `{"type": "status"}` liefert `ok connected` bzw. `ok disconnected`.

In den Pico-Macros gibt es zusätzlich den Typ **LED**. Eingaben:
- `#RRGGBB` (z. B. `#3ecf8e`) setzt alle 8 LEDs auf diese Farbe.
- `off` schaltet den Strip aus.

Auf der **Macros**-Seite kann der LED-Strip außerdem direkt gesteuert werden (Farbe, Anzahl LEDs, Helligkeit, Aus).

Vor dem Einsatz: Keine Spannungen von 5 V auf die Pico-GPIOs legen.

## iCloud-Kalender

Erstelle in den Apple-ID-Einstellungen ein app-spezifisches Passwort. Dieses sowie die Apple-ID können unter **Optionen → iCloud-Kalender** eingetragen werden. Anschließend werden alle verfügbaren iCloud-Kalender geladen und mehrere Kalender können über Kontrollkästchen zur Anzeige ausgewählt werden.
Alternativ können `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD` und `ICLOUD_CALDAV_URL` in `backend/.env` gesetzt werden. Zugangsdaten werden nicht an das Frontend ausgegeben.

## Notion

`backend/.env` aus `backend/.env.example` erstellen und freigegebene Datenbank-IDs eintragen. API-Token und Datenbank-IDs bleiben ausschließlich im Backend.

## Raspberry Pi

`./scripts/install.sh` vorbereitet apt-Abhängigkeiten und einen Desktop-Autostart. Danach werden FastAPI und Chromium über `scripts/start-and-kiosk.sh` gestartet.
