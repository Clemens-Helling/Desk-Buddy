import json
import logging
import os
import sqlite3
from pathlib import Path
from time import monotonic
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env", override=True)
DB_PATH = ROOT / "backend" / "deskbuddy.db"
FRONTEND_DIST = ROOT / "frontend" / "dist"


class _IcloudIcalCompatibilityFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not (
            "Ical data was modified to avoid compatibility issues" in message
            or "Your calendar server breaks the icalendar standard" in message
        )


logging.getLogger().addFilter(_IcloudIcalCompatibilityFilter())

app = FastAPI(title="Deskbuddy API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS notion_cache (kind TEXT PRIMARY KEY, payload TEXT NOT NULL, synced_at TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS pending_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, page_id TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS pico_macros (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0)")


init_db()


def _ensure_default_macros() -> None:
    defaults = [
        ("copy", "Kopieren", "shortcut", json.dumps({"keys": ["CTRL", "C"]}), 0),
        ("paste", "Einfügen", "shortcut", json.dumps({"keys": ["CTRL", "V"]}), 1),
        ("save", "Speichern", "shortcut", json.dumps({"keys": ["CTRL", "S"]}), 2),
    ]
    with db() as connection:
        for macro in defaults:
            connection.execute("INSERT OR IGNORE INTO pico_macros(id,name,kind,payload,sort_order) VALUES(?,?,?,?,?)", macro)


_ensure_default_macros()


def notion_headers() -> dict[str, str]:
    key = os.getenv("NOTION_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Notion ist nicht konfiguriert")
    return {"Authorization": f"Bearer {key}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "notion_configured": bool(os.getenv("NOTION_API_KEY")), "gemini_configured": bool(os.getenv("GEMINI_API_KEY")), "database": str(DB_PATH)}


AVATAR_EVENTS = {"app_started", "timer_started", "timer_completed", "task_completed", "user_clicked_avatar"}
AVATAR_EXPRESSIONS = {"neutral", "happy", "focused", "proud", "sleepy", "thinking", "surprised"}
AVATAR_COLORS = {"default", "focus", "success", "warning"}
_avatar_last_event: float | None = None


def _avatar_fallback(event: str) -> dict[str, str]:
    fallbacks = {
        "app_started": ("happy", "default", "Willkommen", "Bereit für einen guten Tag."),
        "timer_started": ("focused", "focus", "Fokus", "Los geht's – eine Sache nach der anderen."),
        "timer_completed": ("proud", "success", "Geschafft", "Pause verdient!"),
        "task_completed": ("proud", "success", "Super gemacht", "Eine Aufgabe weniger."),
        "user_clicked_avatar": ("happy", "default", "Hi!", "Ich bin bereit."),
    }
    expression, mood_color, badge, message = fallbacks[event]
    return {"expression": expression, "moodColor": mood_color, "badge": badge, "message": message}


@app.post("/api/avatar/event")
async def avatar_event(body: dict[str, Any]) -> dict[str, Any]:
    global _avatar_last_event

    event = str(body.get("event", ""))
    if event not in AVATAR_EVENTS:
        raise HTTPException(status_code=400, detail="Unbekanntes Avatar-Event")

    now = monotonic()
    if _avatar_last_event is not None and now - _avatar_last_event < 15:
        return {"source": "cooldown", **_avatar_fallback(event)}

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    fallback = _avatar_fallback(event)
    if not api_key:
        _avatar_last_event = now
        return {"source": "fallback", **fallback}

    context = str(body.get("context", "Desk Buddy gestartet"))[:300]
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
    prompt = (
        "Du bist der freundliche Avatar eines Raspberry-Pi-Desk-Buddys. "
        "Antworte ausschliesslich als JSON mit exakt diesen Feldern: "
        "expression, moodColor, badge, message. "
        "expression ist eines von neutral|happy|focused|proud|sleepy|thinking|surprised. "
        "moodColor ist eines von default|focus|success|warning. "
        "badge maximal 18 Zeichen. message maximal 70 Zeichen. "
        "Sei kurz, warm und motivierend. Kein Markdown, keine Zusatzerklaerungen. "
        f"Event: {event}. Kontext: {context}"
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 160,
                        "responseMimeType": "application/json",
                    },
                },
            )
            response.raise_for_status()
        candidates = response.json().get("candidates", [])
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
        data = json.loads(text)
        expression = data.get("expression") if data.get("expression") in AVATAR_EXPRESSIONS else fallback["expression"]
        mood_color = data.get("moodColor") if data.get("moodColor") in AVATAR_COLORS else fallback["moodColor"]
        badge = str(data.get("badge", fallback["badge"])).strip()[:18] or fallback["badge"]
        message = str(data.get("message", fallback["message"])).strip()[:70] or fallback["message"]
        _avatar_last_event = now
        return {"source": "gemini", "expression": expression, "moodColor": mood_color, "badge": badge, "message": message}
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        _avatar_last_event = now
        return {"source": "fallback", **fallback}


@app.post("/api/morning/summary")
async def morning_summary() -> dict[str, Any]:
    import json
    from datetime import datetime, timezone

    today = datetime.now().astimezone().date().isoformat()

    with db() as connection:
        task_row = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'").fetchone()
        calendar_row = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'").fetchone()
        weather_row = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='weather'").fetchone()

    tasks = json.loads(task_row["payload"])
    if isinstance(tasks, list):
        today_tasks = [
            str(task.get("title", "Aufgabe"))
            for task in tasks
            if not task.get("done") and (not task.get("due") or str(task.get("due", "")[:10]) == today)
        ]
    else:
        today_tasks = []

    calendar_items = json.loads(calendar_row["payload"]) if calendar_row else []
    today_events = []
    for item in calendar_items if isinstance(calendar_items, list) else []:
        start = str(item.get("start", ""))
        if start[:10] == today:
            time = "Ganztägig" if item.get("all_day") else start[11:16]
            title = str(item.get("title", "Termin"))
            location = str(item.get("location", "")).strip()
            today_events.append(f"{time}: {title}" + (f" ({location})" if location else ""))

    weather = json.loads(weather_row["payload"]) if weather_row else {}

    fallback = "Guten Morgen! "
    if weather:
        fallback += f"Heute {weather.get('temperature')} °C, {weather.get('condition', 'Wetter nicht verfügbar')}. "
    if today_events:
        fallback += f"Als Erstes steht {today_events[0]} an. "
    elif today_tasks:
        fallback += f"Als erste Aufgabe ist {today_tasks[0]} vorgesehen. "
    else:
        fallback += "Heute stehen keine Termine oder Aufgaben an."

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"source": "fallback", "summary": fallback[:500]}

    prompt = (
        "Erstelle eine kurze freundliche Morgen-Zusammenfassung auf Deutsch für einen Desk Buddy. "
        "Berücksichtige das heutige Wetter, Termine und offene Aufgaben. "
        "Antworte nur als JSON mit exakt dem Feld summary. "
        "Maximal 500 Zeichen. Keine Markdown-Aufzählungen, keine Grußformel außerhalb des JSON. "
        f"Datum: {today}. Wetter: {weather}. Termine heute: {today_events}. "
        f"Offene Aufgaben heute: {today_tasks}."
    )

    try:
        model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.6,
                        "maxOutputTokens": 300,
                        "responseMimeType": "application/json",
                    },
                },
            )
            response.raise_for_status()
        candidates = response.json().get("candidates", [])
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
        data = json.loads(text)
        summary = str(data.get("summary", "")).strip()[:500]
        if not summary:
            raise ValueError("Leere Morgen-Zusammenfassung")
        return {"source": "gemini", "summary": summary}
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return {"source": "fallback", "summary": fallback[:500]}


@app.get("/api/tasks")
async def get_tasks() -> dict[str, Any]:
    database_id = os.getenv("NOTION_TASKS_DATABASE_ID", "")
    if not database_id:
        with db() as connection:
            row = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'").fetchone()
        if row:
            import json
            return {"items": json.loads(row["payload"]), "synced_at": row["synced_at"]}
        return {"items": [], "synced_at": None, "offline": True}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=notion_headers(),
                json={"sorts": [{"timestamp": "last_edited_time", "direction": "descending"}]},
            )
            response.raise_for_status()
        import json
        from datetime import datetime, timezone

        items = []
        for page in response.json().get("results", []):
            properties = page.get("properties", {})
            title = "Unbenannte Aufgabe"
            for prop in properties.values():
                if prop.get("type") == "title":
                    title_parts = prop.get("title", [])
                    title = "".join(part.get("plain_text", "") for part in title_parts) or title
                    break
            status_prop = properties.get("Status", {}).get("status")
            status = status_prop.get("name") if status_prop else properties.get("Status", {}).get("select", {}).get("name")
            due_prop = properties.get("Fälligkeitsdatum", {})
            due = (due_prop.get("date") or {}).get("start") if due_prop.get("type") == "date" else None
            due_date = due[:10] if due else None
            today = datetime.now().astimezone().date().isoformat()
            if due_date == today:
                items.append({"id": page["id"], "title": title, "status": status or "Nicht begonnen", "due": due, "done": (status or "").lower() in {"done", "erledigt", "completed"}})

        synced_at = datetime.now(timezone.utc).isoformat()
        with db() as connection:
            connection.execute("INSERT INTO notion_cache(kind,payload,synced_at) VALUES('tasks',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at", (json.dumps(items), synced_at))
        return {"items": items, "synced_at": synced_at}
    except httpx.HTTPError:
        with db() as connection:
            row = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'").fetchone()
        if row:
            import json
            return {"items": json.loads(row["payload"]), "synced_at": row["synced_at"], "offline": True}
        raise HTTPException(status_code=502, detail="Notion ist derzeit nicht erreichbar")


@app.put("/api/tasks/{page_id}/status")
def set_task_status(page_id: str, body: dict[str, str]) -> dict[str, str]:
    status = body.get("status", "").strip()
    if status not in {"Nicht begonnen", "Begonnen", "Erledigt"}:
        raise HTTPException(status_code=400, detail="Ungültiger Aufgabenstatus")
    key = os.getenv("NOTION_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Notion ist nicht konfiguriert")

    try:
        page_response = httpx.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=notion_headers(),
            timeout=10,
        )
        page_response.raise_for_status()
        properties = page_response.json().get("properties", {})
        status_property = None
        status_type = None
        for name, prop in properties.items():
            if name.lower() == "status" or prop.get("type") == "status":
                status_property = name
                status_type = prop.get("type")
                break

        if not status_property:
            for name, prop in properties.items():
                if prop.get("type") == "select":
                    status_property = name
                    status_type = "select"
                    break

        if not status_property:
            raise HTTPException(status_code=422, detail="Die Datenbank hat keine Status- oder Select-Eigenschaft")

        status_value = {"name": status}
        property_value = {"status": status_value} if status_type == "status" else {"select": status_value}
        response = httpx.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=notion_headers(),
            json={"properties": {status_property: property_value}},
            timeout=10,
        )
        response.raise_for_status()
        return {"status": status}
    except httpx.HTTPError:
        with db() as connection:
            connection.execute("INSERT INTO pending_changes(page_id,action,payload,created_at) VALUES(?,?,?,datetime('now'))", (page_id, "status", status))
        return {"status": "pending"}


@app.post("/api/tasks/{page_id}/complete")
def complete_task(page_id: str) -> dict[str, str]:
    key = os.getenv("NOTION_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Notion ist nicht konfiguriert")
    try:
        response = httpx.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=notion_headers(),
            json={"properties": {"Status": {"status": {"name": "Erledigt"}}}},
            timeout=10,
        )
        response.raise_for_status()
        return {"status": "completed"}
    except httpx.HTTPError:
        with db() as connection:
            connection.execute("INSERT INTO pending_changes(page_id,action,payload,created_at) VALUES(?,?,?,datetime('now'))", (page_id, "complete", "{}"))
        return {"status": "pending"}


def _icloud_credentials() -> tuple[str, str]:
    with db() as connection:
        username_row = connection.execute("SELECT value FROM settings WHERE key='icloudUsername'").fetchone()
        password_row = connection.execute("SELECT value FROM settings WHERE key='icloudAppPassword'").fetchone()
    username = (username_row["value"] if username_row else os.getenv("ICLOUD_USERNAME", "")).strip()
    password = (password_row["value"] if password_row else os.getenv("ICLOUD_APP_PASSWORD", "")).strip()
    return username, password


@app.get("/api/calendar/calendars")
def get_icloud_calendars() -> dict[str, Any]:
    username, password = _icloud_credentials()
    if not username or not password:
        return {"items": [], "configured": False, "message": "iCloud-Zugangsdaten fehlen"}

    try:
        from caldav import DAVClient

        client = DAVClient(
            url=os.getenv("ICLOUD_CALDAV_URL", "https://caldav.icloud.com"),
            username=username,
            password=password,
        )
        calendars = client.principal().calendars()
        items = []
        for calendar in calendars:
            name = str(getattr(calendar, "name", "") or "").strip()
            url = str(calendar.url)
            if url:
                items.append({"name": name or "Unbenannter Kalender", "url": url})
        return {"items": items, "configured": True}
    except Exception:
        return {"items": [], "configured": True, "error": "iCloud-Verbindung fehlgeschlagen"}


class IcloudCalendarConfig(BaseModel):
    username: str = ""
    password: str = ""
    calendarUrls: list[str] = []


@app.put("/api/calendar/config")
def set_icloud_calendar(body: IcloudCalendarConfig) -> dict[str, Any]:
    username = body.username.strip()
    password = body.password.strip()
    calendar_urls = body.calendarUrls
    if not isinstance(calendar_urls, list):
        calendar_urls = []
    calendar_urls = [str(url).strip() for url in calendar_urls if str(url).strip()]

    with db() as connection:
        if username:
            connection.execute("INSERT INTO settings(key,value) VALUES('icloudUsername',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (username,))
        if password:
            connection.execute("INSERT INTO settings(key,value) VALUES('icloudAppPassword',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (password,))
        connection.execute("INSERT INTO settings(key,value) VALUES('icloudCalendarUrls',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(calendar_urls),))

    return {"status": "saved", "configured": bool(username or _icloud_credentials()[0])}


@app.get("/api/calendar")
def calendar() -> dict[str, Any]:
    username, password = _icloud_credentials()
    if not username or not password:
        with db() as connection:
            cached = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'").fetchone()
        if cached:
            return {"items": json.loads(cached["payload"]), "configured": False, "synced_at": cached["synced_at"], "offline": True}
        return {"items": [], "configured": False, "synced_at": None}

    try:
        from caldav import DAVClient
        from datetime import datetime, timedelta, timezone

        client = DAVClient(
            url=os.getenv("ICLOUD_CALDAV_URL", "https://caldav.icloud.com"),
            username=username,
            password=password,
        )
        principal = client.principal()

        with db() as connection:
            selected_row = connection.execute("SELECT value FROM settings WHERE key='icloudCalendarUrls'").fetchone()
        try:
            selected_urls = json.loads(selected_row["value"]) if selected_row else []
        except (TypeError, json.JSONDecodeError):
            selected_urls = []
        if not isinstance(selected_urls, list):
            selected_urls = []

        calendars = principal.calendars()
        selected = [candidate for candidate in calendars if str(candidate.url) in selected_urls]
        if not selected_row and calendars:
            selected = calendars[:1]

        if not selected:
            raise RuntimeError("Keine iCloud-Kalender gefunden")

        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=14)
        items = []
        for calendar in selected:
            calendar_name = str(getattr(calendar, "name", "") or "Kalender").strip()
            events = calendar.search(start=start, end=end, event=True, expand=True)
            for event in events:
                icalendar_instance = getattr(event, "icalendar_instance", None)
                if icalendar_instance is None:
                    continue
                for component in icalendar_instance.walk("VEVENT"):
                    title = str(component.get("SUMMARY", "Termin") or "Termin")
                    dtstart = component.decoded("DTSTART") if component.get("DTSTART") else None
                    dtend = component.decoded("DTEND") if component.get("DTEND") else None
                    if dtstart is None:
                        continue
                    if hasattr(dtstart, "isoformat"):
                        start_text = dtstart.isoformat()
                    else:
                        start_text = str(dtstart)
                    if hasattr(dtend, "isoformat"):
                        end_text = dtend.isoformat()
                    else:
                        end_text = str(dtend) if dtend else None
                    items.append({
                        "title": title,
                        "start": start_text,
                        "end": end_text,
                        "location": str(component.get("LOCATION", "") or ""),
                        "all_day": not hasattr(dtstart, "hour"),
                        "calendarName": calendar_name,
                    })

        items.sort(key=lambda item: item["start"])
        synced_at = datetime.now(timezone.utc).isoformat()
        with db() as connection:
            connection.execute("INSERT INTO notion_cache(kind,payload,synced_at) VALUES('calendar',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at", (json.dumps(items), synced_at))
        return {"items": items, "configured": True, "synced_at": synced_at}
    except Exception:
        with db() as connection:
            cached = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'").fetchone()
        if cached:
            return {"items": json.loads(cached["payload"]), "configured": True, "synced_at": cached["synced_at"], "offline": True}
        return {"items": [], "configured": True, "synced_at": None, "offline": True, "error": "iCloud-Kalender nicht erreichbar"}


@app.get("/api/notes")
def notes() -> dict[str, Any]:
    return {"items": [], "configured": bool(os.getenv("NOTION_NOTES_DATABASE_ID")), "synced_at": None}


@app.post("/api/notes")
def create_note(note: dict[str, str]) -> dict[str, str]:
    text = note.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Notiz darf nicht leer sein")
    return {"status": "pending" if not os.getenv("NOTION_NOTES_DATABASE_ID") else "queued", "text": text}


@app.get("/api/notion/test")
async def test_notion() -> dict[str, str]:
    if not os.getenv("NOTION_API_KEY", ""):
        return {"status": "missing", "message": "NOTION_API_KEY ist nicht gesetzt"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get("https://api.notion.com/v1/users/me", headers=notion_headers())
            response.raise_for_status()
        return {"status": "ok", "message": "Verbindung erfolgreich"}
    except httpx.HTTPError:
        return {"status": "error", "message": "Verbindung fehlgeschlagen"}


@app.get("/api/system/brightness")
def get_brightness() -> dict[str, int]:
    backlight = next(iter(sorted(Path("/sys/class/backlight").glob("*"))), None)
    if backlight:
        try:
            current = int((backlight / "brightness").read_text().strip())
            maximum = int((backlight / "max_brightness").read_text().strip())
            return {"brightness": round(current * 100 / maximum)}
        except (OSError, ValueError, ZeroDivisionError):
            pass
    with db() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key='brightness'").fetchone()
    return {"brightness": int(row["value"]) if row else 70}


@app.put("/api/system/brightness")
def set_brightness(body: dict[str, int]) -> dict[str, int | bool]:
    value = max(1, min(100, int(body.get("brightness", 70))))
    backlight = next(iter(sorted(Path("/sys/class/backlight").glob("*"))), None)
    applied = False
    if backlight:
        try:
            maximum = int((backlight / "max_brightness").read_text().strip())
            target = max(1, round(value * maximum / 100))
            (backlight / "brightness").write_text(str(target))
            applied = True
        except (OSError, ValueError, ZeroDivisionError):
            pass
    with db() as connection:
        connection.execute("INSERT INTO settings(key,value) VALUES('brightness',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(value),))
    return {"brightness": value, "applied": applied}


@app.put("/api/system/display")
def set_display(body: dict[str, bool]) -> dict[str, bool | int]:
    enabled = body.get("enabled", True)
    backlight = next(iter(sorted(Path("/sys/class/backlight").glob("*"))), None)
    applied = False

    with db() as connection:
        saved_row = connection.execute("SELECT value FROM settings WHERE key='brightness'").fetchone()
    saved_brightness = int(saved_row["value"]) if saved_row else 70

    if backlight:
        try:
            maximum = int((backlight / "max_brightness").read_text().strip())
            if enabled:
                target = max(1, round(saved_brightness * maximum / 100))
                (backlight / "brightness").write_text(str(target))
            else:
                (backlight / "brightness").write_text("0")
            applied = True
        except (OSError, ValueError, ZeroDivisionError):
            pass

    with db() as connection:
        connection.execute("INSERT INTO settings(key,value) VALUES('displayEnabled',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ("true" if enabled else "false",))
    return {"enabled": enabled, "applied": applied, "brightness": saved_brightness}


@app.get("/api/system/display")
def get_display() -> dict[str, bool]:
    with db() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key='displayEnabled'").fetchone()
    return {"enabled": row["value"] != "false" if row else True}


class PicoMacro(BaseModel):
    id: str
    name: str
    kind: str = "shortcut"
    payload: dict[str, Any] = {}


class PicoMacroConfig(BaseModel):
    macros: list[PicoMacro]


class PicoConfig(BaseModel):
    port: str = "/dev/serial0"
    baud: int = 115200


def _parse_led_color(value: Any) -> list[int]:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) == 6:
            try:
                return [int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)]
            except ValueError:
                pass
        return [255, 255, 255]
    if isinstance(value, list) and len(value) >= 3:
        rgb: list[int] = []
        for item in value[:3]:
            try:
                rgb.append(max(0, min(255, int(item))))
            except (TypeError, ValueError):
                rgb.append(0)
        return rgb
    return [255, 255, 255]


def _build_led_command(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode", "fill")).strip().lower()
    if mode == "off":
        return {"type": "led", "mode": "off"}

    try:
        brightness = max(0.0, min(1.0, float(payload.get("brightness", 0.25))))
    except (TypeError, ValueError):
        brightness = 0.25

    if mode == "pixels":
        pixels = payload.get("pixels", [])
        normalized: list[list[int]] = []
        if isinstance(pixels, list):
            for pixel in pixels[:8]:
                if isinstance(pixel, list):
                    normalized.append(_parse_led_color(pixel))
        return {"type": "led", "mode": "pixels", "pixels": normalized, "brightness": brightness}

    try:
        count = max(0, min(8, int(payload.get("count", 8))))
    except (TypeError, ValueError):
        count = 8

    return {
        "type": "led",
        "mode": "fill",
        "color": _parse_led_color(payload.get("color", "#3ecf8e")),
        "count": count,
        "brightness": brightness,
    }


@app.get("/api/pico/status")
def pico_status() -> dict[str, Any]:
    with db() as connection:
        port_row = connection.execute("SELECT value FROM settings WHERE key='picoPort'").fetchone()
        baud_row = connection.execute("SELECT value FROM settings WHERE key='picoBaud'").fetchone()
    port = port_row["value"] if port_row else os.getenv("PICO_UART_PORT", "/dev/serial0")
    baud = int(baud_row["value"] if baud_row else os.getenv("PICO_UART_BAUD", "115200") or "115200")
    exists = Path(port).exists()
    return {"connected": exists, "port": port, "baud": baud, "message": "Pico-Gerät gefunden" if exists else "Pico nicht gefunden"}


@app.get("/api/pico/config")
def get_pico_config() -> dict[str, Any]:
    with db() as connection:
        port_row = connection.execute("SELECT value FROM settings WHERE key='picoPort'").fetchone()
        baud_row = connection.execute("SELECT value FROM settings WHERE key='picoBaud'").fetchone()
    return {
        "port": port_row["value"] if port_row else os.getenv("PICO_UART_PORT", "/dev/serial0"),
        "baud": int(baud_row["value"] if baud_row else os.getenv("PICO_UART_BAUD", "115200") or "115200"),
    }


@app.put("/api/pico/config")
def set_pico_config(body: PicoConfig) -> dict[str, Any]:
    port = body.port.strip() or "/dev/serial0"
    baud = max(1200, min(921600, body.baud))
    with db() as connection:
        connection.execute("INSERT INTO settings(key,value) VALUES('picoPort',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (port,))
        connection.execute("INSERT INTO settings(key,value) VALUES('picoBaud',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(baud),))
    return {"port": port, "baud": baud}


@app.get("/api/pico/macros")
def get_pico_macros() -> dict[str, Any]:
    with db() as connection:
        rows = connection.execute("SELECT id,name,kind,payload,sort_order FROM pico_macros ORDER BY sort_order,id").fetchall()
    items = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        items.append({"id": row["id"], "name": row["name"], "kind": row["kind"], "payload": payload})
    return {"items": items}


@app.put("/api/pico/macros")
def save_pico_macros(body: PicoMacroConfig) -> dict[str, Any]:
    ids_seen: set[str] = set()
    with db() as connection:
        existing_ids = {row["id"] for row in connection.execute("SELECT id FROM pico_macros").fetchall()}
        for index, macro in enumerate(body.macros):
            macro_id = macro.id.strip() or f"macro-{index + 1}"
            name = macro.name.strip()[:40] or "Unbenanntes Makro"
            kind = macro.kind if macro.kind in {"shortcut", "text", "led"} else "shortcut"
            ids_seen.add(macro_id)
            connection.execute("INSERT INTO pico_macros(id,name,kind,payload,sort_order) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,payload=excluded.payload,sort_order=excluded.sort_order", (macro_id, name, kind, json.dumps(macro.payload), index))
        for old_id in existing_ids - ids_seen:
            connection.execute("DELETE FROM pico_macros WHERE id=?", (old_id,))
    return {"status": "saved", "count": len(ids_seen)}


@app.post("/api/pico/macros/{macro_id}/send")
def send_pico_macro(macro_id: str) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT id,name,kind,payload FROM pico_macros WHERE id=?", (macro_id,)).fetchone()
        port_row = connection.execute("SELECT value FROM settings WHERE key='picoPort'").fetchone()
        baud_row = connection.execute("SELECT value FROM settings WHERE key='picoBaud'").fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Makro nicht gefunden")

    port = port_row["value"] if port_row else os.getenv("PICO_UART_PORT", "/dev/serial0")
    baud = int(baud_row["value"] if baud_row else os.getenv("PICO_UART_BAUD", "115200") or "115200")
    try:
        payload = json.loads(row["payload"])
        if row["kind"] == "text":
            command = {"type": "text", "text": str(payload.get("text", ""))[:500]}
        elif row["kind"] == "led":
            command = _build_led_command(payload)
        else:
            keys = [str(key).strip().upper() for key in payload.get("keys", []) if str(key).strip()][:8]
            command = {"type": "shortcut", "keys": keys}

        import serial
        with serial.Serial(port, baud, timeout=1) as connection:
            connection.write((json.dumps(command, ensure_ascii=False) + "\n").encode("utf-8"))
            connection.flush()
            response = connection.readline().decode("utf-8", errors="replace").strip()
        if response and not response.startswith("ok"):
            raise RuntimeError(response)
        return {"status": "sent", "macro": row["name"]}
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"Pico nicht erreichbar: {exc}")


@app.get("/api/weather")
async def get_weather() -> dict[str, Any]:
    import json
    from datetime import datetime, timezone

    with db() as connection:
        key_row = connection.execute("SELECT value FROM settings WHERE key='weatherApiKey'").fetchone()
        city_row = connection.execute("SELECT value FROM settings WHERE key='weatherCity'").fetchone()

    key = (key_row["value"] if key_row else os.getenv("OPENWEATHER_API_KEY", "")).strip()
    city = (city_row["value"] if city_row else os.getenv("OPENWEATHER_CITY", "Berlin")).strip() or "Berlin"

    with db() as connection:
        cached = connection.execute("SELECT payload, synced_at FROM notion_cache WHERE kind='weather'").fetchone()

    if not key:
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {"status": "missing", "temperature": None, "condition": "Wetter nicht konfiguriert", "icon": "unknown", "city": city}

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": key, "units": "metric", "lang": "de"},
            )
            response.raise_for_status()
            data = response.json()

        result = {
            "status": "ok",
            "temperature": round(float(data["main"]["temp"])),
            "feels_like": round(float(data["main"]["feels_like"])),
            "condition": data["weather"][0]["description"].capitalize() if data.get("weather") else "Unbekannt",
            "icon": data["weather"][0]["icon"] if data.get("weather") else "unknown",
            "city": data.get("name", city),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        with db() as connection:
            connection.execute("INSERT INTO notion_cache(kind,payload,synced_at) VALUES('weather',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at", (json.dumps(result), result["synced_at"]))
        return result
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return {"status": "error", "temperature": None, "condition": "OpenWeather API-Key ungültig", "icon": "unknown", "city": city}
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {"status": "error", "temperature": None, "condition": "Wetterdaten nicht erreichbar", "icon": "unknown", "city": city}
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {"status": "error", "temperature": None, "condition": "Wetterdaten nicht erreichbar", "icon": "unknown", "city": city}


@app.put("/api/weather/config")
def set_weather_config(body: dict[str, str]) -> dict[str, str]:
    key = body.get("apiKey", "").strip()
    city = body.get("city", "").strip()
    with db() as connection:
        if key:
            connection.execute("INSERT INTO settings(key,value) VALUES('weatherApiKey',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,))
        if city:
            connection.execute("INSERT INTO settings(key,value) VALUES('weatherCity',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (city,))
    return {"status": "saved", "configured": bool(key or os.getenv("OPENWEATHER_API_KEY", "")), "city": city}


@app.get("/api/settings")
def get_settings() -> dict[str, str]:
    with db() as connection:
        rows = connection.execute("SELECT key,value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows if row["key"] not in {"weatherApiKey", "notionApiKey", "icloudAppPassword"}}


@app.put("/api/settings/{key}")
def set_setting(key: str, value: dict[str, str]) -> dict[str, str]:
    if not value.get("value"):
        raise HTTPException(status_code=400, detail="Wert fehlt")
    with db() as connection:
        connection.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value["value"]))
    return {"key": key, "value": value["value"]}


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
