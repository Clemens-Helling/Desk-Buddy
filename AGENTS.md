# AGENTS.md – Deskbuddy Raspberry Pi 4

## 1. Projektbeschreibung

Entwickle einen digitalen Deskbuddy für den Raspberry Pi 4 mit einem
7-Zoll-Touchdisplay.

Das Projekt orientiert sich visuell und konzeptionell an:

https://kumiki.xyz/

Der Deskbuddy soll ein kleiner digitaler Schreibtischbegleiter sein,
der Persönlichkeit vermittelt und gleichzeitig praktische Funktionen
für den Alltag bietet.

Er soll nicht wie ein gewöhnliches Dashboard oder ein klassisches
Smart-Home-Bedienpanel aussehen.

Das Gesicht des Deskbuddy ist das zentrale Element der Anwendung.

Der Benutzer soll das Gefühl haben, einen kleinen digitalen Begleiter
auf seinem Schreibtisch stehen zu haben.

### Grundidee

- Ein animiertes Gesicht mit Augen und unterschiedlichen Emotionen.
- Eine große, gut lesbare Uhr.
- Datum und Wochentag.
- Pomodoro-Timer.
- Wetteranzeige.
- Kleine, austauschbare Widgets.
- Touchbedienung.
- Einstellbare Darstellung und Persönlichkeit.
- Dauerbetrieb auf einem Raspberry Pi 4.

## 2. Designreferenz

Die wichtigste Designreferenz ist Kumiki:

https://kumiki.xyz/

Übernimm die gestalterische Richtung und das Gefühl des Projektes,
ohne die Website einfach zu kopieren.

### Gewünschte Designmerkmale

- Minimalistisch
- Freundlich
- Verspielt
- Modern
- Sympathisch
- Organische Formen
- Große, klare Elemente
- Dezente Animationen
- Hochwertige visuelle Gestaltung

Die Anwendung soll wie ein eigenständiges kleines Produkt wirken.

Vermeide:

- Klassische Admin-Dashboards.
- Überladene Informationsanzeigen.
- Zu viele kleine Bedienelemente.
- Typische Bootstrap- oder Standard-Webapp-Optik.
- Unnötige Verläufe und starke Schatten.
- Zu viele gleichzeitig sichtbare Informationen.

## 3. Hardware

Zielhardware:

- Raspberry Pi 4
- 7-Zoll-Touchdisplay
- Raspberry Pi OS
- Lokaler Betrieb ohne Cloud-Abhängigkeit
- Dauerbetrieb im Vollbildmodus

### Display

Das Interface muss speziell für ein 7-Zoll-Display optimiert werden.

Wichtig:

- Displayauflösung zur Laufzeit erkennen.
- Keine feste Desktop-Auflösung voraussetzen.
- Touchbedienung berücksichtigen.
- Alle wichtigen Elemente müssen ohne Scrollen erreichbar sein.
- Schriftgrößen müssen aus normaler Betrachtungsdistanz lesbar sein.
- Ausreichend große Touchflächen verwenden.
- Keine Hover-abhängigen Funktionen.
- Keine wichtigen Elemente am äußersten Bildschirmrand platzieren.

Die Oberfläche muss sowohl im Querformat als auch bei Bedarf
im Hochformat funktionieren.

Primäres Ziel ist zunächst Querformat.

## 4. Technische Architektur

Bevorzugte Architektur:

### Frontend

- React
- TypeScript
- Vite
- CSS oder CSS Modules
- SVG für das animierte Gesicht
- Lucide Icons für passende Bedienelemente

### Backend

- Python
- Lokale REST-API
- Optional WebSocket für Echtzeitaktualisierungen
- SQLite für lokale Einstellungen und Daten

### Betrieb

- Raspberry Pi OS
- Chromium im Kiosk-Modus
- Automatischer Programmstart nach dem Booten
- Vollbild ohne Browserleisten
- Lokaler Betrieb über localhost

Die Anwendung muss ressourcenschonend sein.

Keine unnötig großen Bibliotheken oder aufwendigen Animationen
verwenden.

Wenn eine einfachere technische Lösung ausreicht, ist diese zu bevorzugen.

## 5. Hauptbildschirm

Der Hauptbildschirm ist das Herzstück des Deskbuddy.

Er soll auf einen Blick die wichtigsten Informationen darstellen.

### Aufbau

1. Gesicht des Deskbuddy
2. Große Uhrzeit
3. Datum
4. Wetterinformation
5. Pomodoro-Status
6. Kleine Statusinformationen

Die genaue Anordnung soll speziell für das 7-Zoll-Display
entwickelt werden.

Das Gesicht soll optisch dominieren.

Die Informationen sollen das Gesicht ergänzen und nicht
mit ihm konkurrieren.

### Gesicht und Persönlichkeit

Das Gesicht ist das wichtigste Designelement.

Es soll über SVG oder eine vergleichbare performante Lösung
realisiert werden.

Folgende Gesichtsausdrücke sollen möglich sein:

- Neutral
- Glücklich
- Müde
- Schlafend
- Konzentriert
- Überrascht
- Traurig
- Aufgeregt

Die Augen sollen animiert werden können.

Mögliche Animationen:

- Blinzeln
- Blickbewegungen
- Leichtes Wackeln
- Reaktion auf Touch
- Übergang zwischen Gesichtsausdrücken
- Schlafanimation

Animationen müssen dezent und flüssig sein.

Keine permanenten aufwendigen Animationen verwenden.

Das Gesicht soll einen eigenen Charakter bekommen.

## 6. Funktionen

### Uhr

- Große digitale Uhrzeit
- 24-Stunden-Format
- Datum
- Wochentag
- Optional Sekunden
- Automatische Aktualisierung

### Pomodoro

Ein integrierter Pomodoro-Timer.

Funktionen:

- Arbeitsphase
- Kurze Pause
- Lange Pause
- Start
- Pause
- Fortsetzen
- Zurücksetzen
- Einstellbare Zeitintervalle

Der Deskbuddy soll während einer Arbeitsphase
einen konzentrierten Gesichtsausdruck zeigen.

Während einer Pause darf er entspannter wirken.

### Wetter

- Aktuelle Temperatur
- Wetterzustand
- Wetter-Icon
- Optional Tageshöchst- und Tiefsttemperatur

Wetterdaten müssen über eine austauschbare API angebunden werden.

Die Anwendung muss auch ohne Internetverbindung
weiter funktionieren.

### Widgets

Die Anwendung soll modular aufgebaut werden.

Geplante Widgets:

- Uhr
- Wetter
- Pomodoro
- Kalender
- Aufgaben
- Erinnerungen
- Systeminformationen

Widgets sollen später einfach ergänzt oder entfernt werden können.

Jedes Widget soll eine klar definierte Schnittstelle besitzen.

## 7. Navigation und Touchbedienung

Die Bedienung erfolgt hauptsächlich über Touch.

Die Oberfläche soll möglichst ohne komplizierte Menüs auskommen.

Geplante Bereiche:

- Home
- Widgets
- Timer
- Einstellungen

Navigation soll intuitiv und mit wenigen Berührungen
möglich sein.

Einstellungen können über ein dezentes Zahnrad-Symbol
erreicht werden.

Wichtige Touchflächen sollten mindestens ungefähr
48 x 48 CSS-Pixel groß sein.

## 8. Visuelles Design

### Farbgestaltung

Entwickle ein harmonisches Farbsystem, das sich an der
freundlichen und reduzierten Kumiki-Ästhetik orientiert.

Bevorzugt:

- Warme helle Hintergründe
- Dunkle, gut lesbare Texte
- Dezente Akzentfarben
- Pastellige Sekundärfarben
- Optional ein dunkles Theme

Farben sollen konsistent eingesetzt werden.

### Komponenten

Alle UI-Komponenten müssen einem gemeinsamen
Designsystem folgen.

Dazu gehören:

- Buttons
- Karten
- Statusanzeigen
- Timer
- Icons
- Widget-Container
- Einstellungsdialoge

Keine zufällig zusammengestellten Komponenten verwenden.

### Typografie

- Gut lesbare moderne Schrift
- Klare Hierarchie
- Große Uhrzeit
- Wenig Fließtext
- Gute Lesbarkeit auf 7 Zoll

## 9. Performance

Der Raspberry Pi 4 besitzt begrenzte Ressourcen.

Deshalb gelten folgende Regeln:

- Möglichst geringe CPU-Auslastung.
- RAM-Verbrauch niedrig halten.
- Keine unnötigen Hintergrundprozesse.
- Animationen über CSS oder SVG realisieren.
- Keine unnötigen React-Re-Renders.
- Daten nur bei Bedarf aktualisieren.
- API-Abfragen zwischenspeichern.
- Keine permanenten Netzwerkabfragen.
- Bei fehlender Internetverbindung weiterarbeiten.
- Stabiler Betrieb über mehrere Tage.

Ziel ist eine flüssige Bedienung bei möglichst geringer
Systembelastung.

## 10. Offlinefähigkeit

Der Deskbuddy muss auch ohne Internetverbindung
verwendbar sein.

Folgende Funktionen müssen lokal funktionieren:

- Uhr
- Datum
- Pomodoro
- Gesichtsausdrücke
- Navigation
- Einstellungen
- Lokale Widgets

Onlinefunktionen wie Wetter dürfen bei fehlender
Verbindung eine entsprechende Statusanzeige zeigen.

Keine Funktion darf dazu führen, dass die gesamte
Anwendung bei einem Netzwerkausfall abstürzt.

## 11. Projektstruktur

Eine mögliche Projektstruktur:

deskbuddy/
│
├── GEMINI.md
├── package.json
├── vite.config.ts
│
├── frontend/
│ └── src/
│ ├── components/
│ │ ├── BuddyFace/
│ │ ├── Clock/
│ │ ├── Weather/
│ │ ├── Pomodoro/
│ │ └── Navigation/
│ │
│ ├── widgets/
│ ├── pages/
│ ├── hooks/
│ ├── services/
│ ├── styles/
│ ├── assets/
│ └── App.tsx
│
├── backend/
│ ├── main.py
│ ├── api/
│ ├── services/
│ ├── database/
│ └── config/
│
├── scripts/
│ ├── install.sh
│ ├── start.sh
│ └── kiosk.sh
│
└── docs/

Die tatsächliche Struktur darf angepasst werden,
wenn eine bessere Architektur sinnvoll ist.

## 12. Entwicklungsregeln

- Schreibe sauberen und verständlichen Code.
- Verwende TypeScript konsequent.
- Komponenten sollen möglichst klein und wiederverwendbar sein.
- Trenne Darstellung und Geschäftslogik.
- Verwende keine unnötigen Abhängigkeiten.
- Behandle Fehler und fehlende Netzwerkverbindungen.
- Dokumentiere wichtige Funktionen.
- Vermeide unnötige Komplexität.
- Achte auf langfristige Wartbarkeit.

Vorhandene Funktionen dürfen bei neuen Änderungen
nicht unbeabsichtigt beschädigt werden.

## 13. Vorgehensweise

Entwickle das Projekt schrittweise.

### Phase 1 – Grundgerüst

- React-Projekt erstellen.
- Grundlegendes Designsystem einrichten.
- Displayoptimiertes Layout entwickeln.
- Hauptbildschirm implementieren.

### Phase 2 – Buddy Face

- Gesicht als eigenständige Komponente erstellen.
- Augen und Gesichtsausdrücke implementieren.
- Blinzelanimation entwickeln.
- Touchreaktionen hinzufügen.

### Phase 3 – Basisfunktionen

- Uhr
- Datum
- Pomodoro-Timer
- Wetter-Widget

### Phase 4 – Erweiterungen

- Widget-System
- Kalender
- Aufgaben
- Einstellungen
- Dark Mode

### Phase 5 – Raspberry Pi

- Raspberry Pi OS vorbereiten.
- Chromium-Kiosk-Modus einrichten.
- Autostart konfigurieren.
- Performance optimieren.
- Touchbedienung testen.
- Dauerbetrieb testen.

## 14. Qualitätsanforderungen

Das Ergebnis soll sich wie ein fertiges Consumer-Produkt
anfühlen.

Nicht wie ein Entwickler-Dashboard.

Besonders wichtig sind:

1. Ein sympathisches Gesicht mit Charakter.
2. Ein hochwertiges und konsistentes Design.
3. Eine perfekte Anpassung an das 7-Zoll-Display.
4. Intuitive Touchbedienung.
5. Flüssige Animationen.
6. Stabiler Dauerbetrieb.
7. Modulare Erweiterbarkeit.

Bei jeder Designentscheidung gilt:

Der Deskbuddy ist ein kleiner digitaler Freund
auf dem Schreibtisch – kein gewöhnlicher Computerbildschirm.

## 15. Arbeitsanweisung für Gemini

Arbeite immer innerhalb der definierten Designrichtung.

Bevor du neue Komponenten entwickelst:

- Prüfe die vorhandene Projektstruktur.
- Prüfe bestehende Komponenten.
- Verwende vorhandene Design-Tokens.
- Achte auf die Displaygröße.
- Vermeide unnötige Änderungen an funktionierendem Code.

Wenn eine neue Funktion implementiert wird,
soll sie sich optisch und technisch nahtlos
in das bestehende Projekt integrieren.

Priorisiere Benutzererlebnis, Designqualität,
Performance und Stabilität.

## 16. Notion-Integration

Notion ist ein zentraler Bestandteil des Deskbuddy.

Der Deskbuddy soll persönliche Informationen aus dem
eigenen Notion-Workspace abrufen und übersichtlich auf
dem 7-Zoll-Display darstellen.

Die Integration soll sich optisch vollständig in das
Kumiki-inspirierte Design integrieren.

Es soll keine verkleinerte Notion-Webseite angezeigt werden.
Stattdessen werden Notion-Inhalte als native Deskbuddy-
Komponenten dargestellt.

### 16.1 Technische Anbindung

Verwende die offizielle Notion API.

Dokumentation:
https://developers.notion.com/

Die Kommunikation mit Notion erfolgt ausschließlich
über das Python-Backend.

Wichtige Regeln:

- API-Token niemals im Frontend speichern.
- Zugangsdaten in einer lokalen .env-Datei hinterlegen.
- .env niemals in Git einchecken.
- Notion API über FastAPI anbinden.
- Fehler und API-Limits berücksichtigen.
- Daten lokal zwischenspeichern.
- Nur ausdrücklich freigegebene Notion-Seiten und
  Datenbanken verwenden.

Konfiguration über Umgebungsvariablen:

NOTION_API_KEY=
NOTION_TASKS_DATABASE_ID=
NOTION_CALENDAR_DATABASE_ID=
NOTION_NOTES_DATABASE_ID=

Die Datenbank-IDs müssen optional konfigurierbar sein.

### 16.2 Notion-Dashboard

Erstelle einen eigenen Notion-Bereich innerhalb
der Deskbuddy-Anwendung.

Folgende Ansichten sind vorgesehen:

1. Heute
2. Aufgaben
3. Kalender
4. Notizen
5. Projekte

### 16.3 Aufgaben

Die Aufgabenansicht soll folgende Informationen zeigen:

- Aufgabenname
- Status
- Priorität
- Fälligkeitsdatum
- Zugehöriges Projekt

Funktionen:

- Aufgaben aus Notion laden.
- Aufgaben nach Status filtern.
- Aufgaben als erledigt markieren.
- Aufgaben nach Fälligkeit sortieren.
- Überfällige Aufgaben hervorheben.
- Aufgaben direkt auf dem Touchdisplay bedienen.

Änderungen müssen über die Notion API zurück
in Notion geschrieben werden.

### 16.4 Tagesübersicht

Erstelle eine kompakte Tagesübersicht.

Anzeigen:

- Heutiges Datum
- Heutige Aufgaben
- Überfällige Aufgaben
- Anstehende Termine
- Aufgaben für morgen

Die Übersicht soll automatisch aktualisiert werden.

### 16.5 Kalender

Der Kalender soll Notion-Datenbanken mit Datumsfeldern
verwenden können.

Anzeigen:

- Heutige Termine
- Kommende Termine
- Wochenübersicht
- Fällige Aufgaben

Die Darstellung soll speziell für das kleine Display
optimiert sein.

### 16.6 Notizen

Ermögliche den Zugriff auf ausgewählte Notion-Seiten.

Funktionen:

- Letzte Notizen anzeigen.
- Notiztitel und Vorschau anzeigen.
- Notion-Seiten öffnen.
- Neue Schnellnotizen erstellen.
- Schnellnotizen optional einer konfigurierten
  Notion-Datenbank hinzufügen.

### 16.7 Touchbedienung

Die Notion-Ansichten müssen vollständig für Touch
optimiert sein.

- Aufgaben mit einem Fingertipp abhaken.
- Zwischen Ansichten wechseln.
- Inhalte ohne unnötiges Scrollen darstellen.
- Große Touchflächen verwenden.
- Bei langen Listen sanft scrollen.
- Keine Hover-Funktionen voraussetzen.

### 16.8 Synchronisierung

Die Synchronisierung erfolgt im Hintergrund.

Anforderungen:

- Regelmäßige Aktualisierung.
- Manuelle Aktualisierung über Touch.
- Lokaler Cache.
- Anzeige des letzten Synchronisierungszeitpunkts.
- Fehleranzeige bei Verbindungsproblemen.
- Lokale Bedienbarkeit bei Internetausfall.

Änderungen, die offline vorgenommen werden, müssen
als ausstehend gespeichert werden.

Beim nächsten erfolgreichen Verbindungsaufbau
sollen diese Änderungen kontrolliert synchronisiert werden.

Konflikte dürfen nicht stillschweigend Daten überschreiben.

Beachte die Rate Limits der Notion API.

### 16.9 Notion-Konfiguration

Erstelle einen Einstellungsbereich, in dem der Benutzer
die Notion-Integration konfigurieren kann.

Möglichkeiten:

- API-Verbindung testen.
- Aufgaben-Datenbank auswählen.
- Kalender-Datenbank auswählen.
- Notizen-Datenbank auswählen.
- Synchronisierungsintervall einstellen.
- Notion-Verbindung deaktivieren.

### 16.10 Design

Die Notion-Ansichten müssen optisch zum restlichen
Deskbuddy passen.

Verwende:

- Abgerundete Karten
- Dezente Farben
- Minimalistische Icons
- Große lesbare Texte
- Kleine Statusindikatoren
- Klare Informationshierarchie

Notion soll sich wie ein natürlicher Bestandteil
des Deskbuddy anfühlen.

### 16.11 Priorität

Die Notion-Integration ist eine Kernfunktion
des Projekts.

Priorität bei der Entwicklung:

1. Notion API verbinden.
2. Aufgaben-Datenbank abrufen.
3. Aufgaben auf dem Home-Screen anzeigen.
4. Aufgaben als erledigt markieren.
5. Tagesübersicht erstellen.
6. Kalender integrieren.
7. Notizen integrieren.
8. Offline-Synchronisierung ergänzen.
