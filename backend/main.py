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


import socket
import subprocess


try:
    from rpi_ws281x import Color, PixelStrip  # type: ignore
except ImportError:
    Color = None
    PixelStrip = None


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS notion_cache (kind TEXT PRIMARY KEY, payload TEXT NOT NULL, synced_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS pending_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, page_id TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS pico_macros (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0)"
        )


init_db()


def _ensure_default_macros() -> None:
    defaults = [
        ("copy", "Kopieren", "shortcut", json.dumps({"keys": ["CTRL", "C"]}), 0),
        ("paste", "Einfügen", "shortcut", json.dumps({"keys": ["CTRL", "V"]}), 1),
        ("save", "Speichern", "shortcut", json.dumps({"keys": ["CTRL", "S"]}), 2),
    ]
    with db() as connection:
        for macro in defaults:
            connection.execute(
                "INSERT OR IGNORE INTO pico_macros(id,name,kind,payload,sort_order) VALUES(?,?,?,?,?)",
                macro,
            )


_ensure_default_macros()


def notion_headers() -> dict[str, str]:
    key = os.getenv("NOTION_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Notion ist nicht konfiguriert")
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "notion_configured": bool(os.getenv("NOTION_API_KEY")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "database": str(DB_PATH),
    }


AVATAR_EVENTS = {
    "app_started",
    "timer_started",
    "timer_completed",
    "task_completed",
    "user_clicked_avatar",
}
AVATAR_EXPRESSIONS = {
    "neutral",
    "happy",
    "focused",
    "proud",
    "sleepy",
    "thinking",
    "surprised",
}
AVATAR_COLORS = {"default", "focus", "success", "warning"}
_avatar_last_event: float | None = None


def _avatar_fallback(event: str) -> dict[str, str]:
    fallbacks = {
        "app_started": (
            "happy",
            "default",
            "Willkommen",
            "Bereit für einen guten Tag.",
        ),
        "timer_started": (
            "focused",
            "focus",
            "Fokus",
            "Los geht's – eine Sache nach der anderen.",
        ),
        "timer_completed": ("proud", "success", "Geschafft", "Pause verdient!"),
        "task_completed": (
            "proud",
            "success",
            "Super gemacht",
            "Eine Aufgabe weniger.",
        ),
        "user_clicked_avatar": ("happy", "default", "Hi!", "Ich bin bereit."),
    }
    expression, mood_color, badge, message = fallbacks[event]
    return {
        "expression": expression,
        "moodColor": mood_color,
        "badge": badge,
        "message": message,
    }


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
        text = (
            candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if candidates
            else ""
        )
        data = json.loads(text)
        expression = (
            data.get("expression")
            if data.get("expression") in AVATAR_EXPRESSIONS
            else fallback["expression"]
        )
        mood_color = (
            data.get("moodColor")
            if data.get("moodColor") in AVATAR_COLORS
            else fallback["moodColor"]
        )
        badge = (
            str(data.get("badge", fallback["badge"])).strip()[:18] or fallback["badge"]
        )
        message = (
            str(data.get("message", fallback["message"])).strip()[:70]
            or fallback["message"]
        )
        _avatar_last_event = now
        return {
            "source": "gemini",
            "expression": expression,
            "moodColor": mood_color,
            "badge": badge,
            "message": message,
        }
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        _avatar_last_event = now
        return {"source": "fallback", **fallback}


@app.post("/api/morning/summary")
async def morning_summary() -> dict[str, Any]:
    import json
    from datetime import datetime, timezone

    today = datetime.now().astimezone().date().isoformat()

    with db() as connection:
        task_row = connection.execute(
            "SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'"
        ).fetchone()
        calendar_row = connection.execute(
            "SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'"
        ).fetchone()
        weather_row = connection.execute(
            "SELECT payload, synced_at FROM notion_cache WHERE kind='weather'"
        ).fetchone()

    tasks = json.loads(task_row["payload"])
    if isinstance(tasks, list):
        today_tasks = [
            str(task.get("title", "Aufgabe"))
            for task in tasks
            if not task.get("done")
            and (not task.get("due") or str(task.get("due", "")[:10]) == today)
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
            today_events.append(
                f"{time}: {title}" + (f" ({location})" if location else "")
            )

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
        text = (
            candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if candidates
            else ""
        )
        data = json.loads(text)
        summary = str(data.get("summary", "")).strip()[:500]
        if not summary:
            raise ValueError("Leere Morgen-Zusammenfassung")
        return {"source": "gemini", "summary": summary}
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        return {"source": "fallback", "summary": fallback[:500]}


@app.get("/api/tasks")
async def get_tasks() -> dict[str, Any]:
    database_id = os.getenv("NOTION_TASKS_DATABASE_ID", "")
    if not database_id:
        with db() as connection:
            row = connection.execute(
                "SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'"
            ).fetchone()
        if row:
            import json

            return {"items": json.loads(row["payload"]), "synced_at": row["synced_at"]}
        return {"items": [], "synced_at": None, "offline": True}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=notion_headers(),
                json={
                    "sorts": [
                        {"timestamp": "last_edited_time", "direction": "descending"}
                    ]
                },
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
                    title = (
                        "".join(part.get("plain_text", "") for part in title_parts)
                        or title
                    )
                    break
            status_prop = properties.get("Status", {}).get("status")
            status = (
                status_prop.get("name")
                if status_prop
                else properties.get("Status", {}).get("select", {}).get("name")
            )
            due_prop = properties.get("Fälligkeitsdatum", {})
            due = (
                (due_prop.get("date") or {}).get("start")
                if due_prop.get("type") == "date"
                else None
            )
            due_date = due[:10] if due else None
            today = datetime.now().astimezone().date().isoformat()
            if due_date == today:
                items.append(
                    {
                        "id": page["id"],
                        "title": title,
                        "status": status or "Nicht begonnen",
                        "due": due,
                        "done": (status or "").lower()
                        in {"done", "erledigt", "completed"},
                    }
                )

        synced_at = datetime.now(timezone.utc).isoformat()
        with db() as connection:
            connection.execute(
                "INSERT INTO notion_cache(kind,payload,synced_at) VALUES('tasks',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at",
                (json.dumps(items), synced_at),
            )
        return {"items": items, "synced_at": synced_at}
    except httpx.HTTPError:
        with db() as connection:
            row = connection.execute(
                "SELECT payload, synced_at FROM notion_cache WHERE kind='tasks'"
            ).fetchone()
        if row:
            import json

            return {
                "items": json.loads(row["payload"]),
                "synced_at": row["synced_at"],
                "offline": True,
            }
        raise HTTPException(
            status_code=502, detail="Notion ist derzeit nicht erreichbar"
        )


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
            raise HTTPException(
                status_code=422,
                detail="Die Datenbank hat keine Status- oder Select-Eigenschaft",
            )

        status_value = {"name": status}
        property_value = (
            {"status": status_value}
            if status_type == "status"
            else {"select": status_value}
        )
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
            connection.execute(
                "INSERT INTO pending_changes(page_id,action,payload,created_at) VALUES(?,?,?,datetime('now'))",
                (page_id, "status", status),
            )
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
            connection.execute(
                "INSERT INTO pending_changes(page_id,action,payload,created_at) VALUES(?,?,?,datetime('now'))",
                (page_id, "complete", "{}"),
            )
        return {"status": "pending"}


def _icloud_credentials() -> tuple[str, str]:
    with db() as connection:
        username_row = connection.execute(
            "SELECT value FROM settings WHERE key='icloudUsername'"
        ).fetchone()
        password_row = connection.execute(
            "SELECT value FROM settings WHERE key='icloudAppPassword'"
        ).fetchone()
    username = (
        username_row["value"] if username_row else os.getenv("ICLOUD_USERNAME", "")
    ).strip()
    password = (
        password_row["value"] if password_row else os.getenv("ICLOUD_APP_PASSWORD", "")
    ).strip()
    return username, password


@app.get("/api/calendar/calendars")
def get_icloud_calendars() -> dict[str, Any]:
    username, password = _icloud_credentials()
    if not username or not password:
        return {
            "items": [],
            "configured": False,
            "message": "iCloud-Zugangsdaten fehlen",
        }

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
        return {
            "items": [],
            "configured": True,
            "error": "iCloud-Verbindung fehlgeschlagen",
        }


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
            connection.execute(
                "INSERT INTO settings(key,value) VALUES('icloudUsername',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (username,),
            )
        if password:
            connection.execute(
                "INSERT INTO settings(key,value) VALUES('icloudAppPassword',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (password,),
            )
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('icloudCalendarUrls',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(calendar_urls),),
        )

    return {"status": "saved", "configured": bool(username or _icloud_credentials()[0])}


@app.get("/api/calendar")
def calendar() -> dict[str, Any]:
    username, password = _icloud_credentials()
    if not username or not password:
        with db() as connection:
            cached = connection.execute(
                "SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'"
            ).fetchone()
        if cached:
            return {
                "items": json.loads(cached["payload"]),
                "configured": False,
                "synced_at": cached["synced_at"],
                "offline": True,
            }
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
            selected_row = connection.execute(
                "SELECT value FROM settings WHERE key='icloudCalendarUrls'"
            ).fetchone()
        try:
            selected_urls = json.loads(selected_row["value"]) if selected_row else []
        except (TypeError, json.JSONDecodeError):
            selected_urls = []
        if not isinstance(selected_urls, list):
            selected_urls = []

        calendars = principal.calendars()
        selected = [
            candidate for candidate in calendars if str(candidate.url) in selected_urls
        ]
        if not selected_row and calendars:
            selected = calendars[:1]

        if not selected:
            raise RuntimeError("Keine iCloud-Kalender gefunden")

        start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
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
                    dtstart = (
                        component.decoded("DTSTART")
                        if component.get("DTSTART")
                        else None
                    )
                    dtend = (
                        component.decoded("DTEND") if component.get("DTEND") else None
                    )
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
                    items.append(
                        {
                            "title": title,
                            "start": start_text,
                            "end": end_text,
                            "location": str(component.get("LOCATION", "") or ""),
                            "all_day": not hasattr(dtstart, "hour"),
                            "calendarName": calendar_name,
                        }
                    )

        items.sort(key=lambda item: item["start"])
        synced_at = datetime.now(timezone.utc).isoformat()
        with db() as connection:
            connection.execute(
                "INSERT INTO notion_cache(kind,payload,synced_at) VALUES('calendar',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at",
                (json.dumps(items), synced_at),
            )
        return {"items": items, "configured": True, "synced_at": synced_at}
    except Exception:
        with db() as connection:
            cached = connection.execute(
                "SELECT payload, synced_at FROM notion_cache WHERE kind='calendar'"
            ).fetchone()
        if cached:
            return {
                "items": json.loads(cached["payload"]),
                "configured": True,
                "synced_at": cached["synced_at"],
                "offline": True,
            }
        return {
            "items": [],
            "configured": True,
            "synced_at": None,
            "offline": True,
            "error": "iCloud-Kalender nicht erreichbar",
        }


@app.get("/api/notes")
def notes() -> dict[str, Any]:
    return {
        "items": [],
        "configured": bool(os.getenv("NOTION_NOTES_DATABASE_ID")),
        "synced_at": None,
    }


@app.post("/api/notes")
def create_note(note: dict[str, str]) -> dict[str, str]:
    text = note.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Notiz darf nicht leer sein")
    return {
        "status": "pending" if not os.getenv("NOTION_NOTES_DATABASE_ID") else "queued",
        "text": text,
    }


@app.get("/api/notion/test")
async def test_notion() -> dict[str, str]:
    if not os.getenv("NOTION_API_KEY", ""):
        return {"status": "missing", "message": "NOTION_API_KEY ist nicht gesetzt"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://api.notion.com/v1/users/me", headers=notion_headers()
            )
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
        row = connection.execute(
            "SELECT value FROM settings WHERE key='brightness'"
        ).fetchone()
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
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('brightness',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(value),),
        )
    return {"brightness": value, "applied": applied}


@app.put("/api/system/display")
def set_display(body: dict[str, bool]) -> dict[str, bool | int]:
    enabled = body.get("enabled", True)
    backlight = next(iter(sorted(Path("/sys/class/backlight").glob("*"))), None)
    applied = False

    with db() as connection:
        saved_row = connection.execute(
            "SELECT value FROM settings WHERE key='brightness'"
        ).fetchone()
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
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('displayEnabled',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("true" if enabled else "false",),
        )
    return {"enabled": enabled, "applied": applied, "brightness": saved_brightness}


@app.get("/api/system/display")
def get_display() -> dict[str, bool]:
    with db() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key='displayEnabled'"
        ).fetchone()
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


class PicoLedControl(BaseModel):
    mode: str = "fill"
    color: str = "#3ecf8e"
    count: int = 8
    brightness: float = 0.25


# --- LED-Konfiguration (direkt am Raspberry Pi 4) ---

LED_COUNT = int(os.getenv("PI_LED_COUNT", "8"))
LED_PIN = int(os.getenv("PI_LED_PIN", "18"))  # GPIO 18 (PWM0)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_INVERT = False
LED_CHANNEL = 0

L2CAP_PSM_HID_INTERRUPT = 0x13  # Standard Bluetooth HID Interrupt PSM

_strip: Any = None
_hid_interrupt_sock: socket.socket | None = None
_connected_mac: str | None = None


def _get_led_strip(count: int = LED_COUNT, brightness: float = 0.25) -> Any:
    global _strip
    if PixelStrip is None or Color is None:
        raise RuntimeError("Bibliothek 'rpi_ws281x' ist nicht installiert")

    led_brightness = max(0, min(255, int(round(brightness * 255))))
    if _strip is None or _strip.numPixels() != count:
        _strip = PixelStrip(
            count,
            LED_PIN,
            LED_FREQ_HZ,
            LED_DMA,
            LED_INVERT,
            led_brightness,
            LED_CHANNEL,
        )
        _strip.begin()
    else:
        _strip.setBrightness(led_brightness)
    return _strip


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
        return {"type": "led", "mode": "off", "count": LED_COUNT, "brightness": 0.0}

    try:
        brightness = max(0.0, min(1.0, float(payload.get("brightness", 0.25))))
    except (TypeError, ValueError):
        brightness = 0.25

    if mode == "pixels":
        pixels = payload.get("pixels", [])
        normalized: list[list[int]] = []
        if isinstance(pixels, list):
            for pixel in pixels[:64]:
                if isinstance(pixel, list):
                    normalized.append(_parse_led_color(pixel))
        return {
            "type": "led",
            "mode": "pixels",
            "pixels": normalized,
            "count": max(len(normalized), LED_COUNT),
            "brightness": brightness,
        }

    try:
        count = max(0, min(64, int(payload.get("count", LED_COUNT))))
    except (TypeError, ValueError):
        count = LED_COUNT

    return {
        "type": "led",
        "mode": "fill",
        "color": _parse_led_color(payload.get("color", "#3ecf8e")),
        "count": count,
        "brightness": brightness,
    }


def _apply_led_command(command: dict[str, Any]) -> None:
    mode = command.get("mode", "fill")
    count = int(command.get("count", LED_COUNT))
    brightness = float(command.get("brightness", 0.25))
    strip = _get_led_strip(count=max(1, count), brightness=brightness)

    if mode == "off":
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        return

    if mode == "pixels":
        pixels: list[list[int]] = command.get("pixels", [])
        for i in range(strip.numPixels()):
            if i < len(pixels):
                r, g, b = pixels[i]
                strip.setPixelColor(i, Color(r, g, b))
            else:
                strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        return

    r, g, b = command.get("color", [62, 207, 142])
    active_count = min(count, strip.numPixels())
    for i in range(strip.numPixels()):
        if i < active_count:
            strip.setPixelColor(i, Color(r, g, b))
        else:
            strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


# --- Bluetooth-Tastatur über BlueZ (L2CAP HID Interrupt) ---

HID_MODIFIERS: dict[str, int] = {
    "CTRL": 0x01,
    "LCTRL": 0x01,
    "SHIFT": 0x02,
    "LSHIFT": 0x02,
    "ALT": 0x04,
    "LALT": 0x04,
    "META": 0x08,
    "WIN": 0x08,
    "SUPER": 0x08,
    "RCTRL": 0x10,
    "RSHIFT": 0x20,
    "RALT": 0x40,
    "ALTGR": 0x40,
}

HID_KEYCODES: dict[str, int] = {
    "A": 0x04,
    "B": 0x05,
    "C": 0x06,
    "D": 0x07,
    "E": 0x08,
    "F": 0x09,
    "G": 0x0A,
    "H": 0x0B,
    "I": 0x0C,
    "J": 0x0D,
    "K": 0x0E,
    "L": 0x0F,
    "M": 0x10,
    "N": 0x11,
    "O": 0x12,
    "P": 0x13,
    "Q": 0x14,
    "R": 0x15,
    "S": 0x16,
    "T": 0x17,
    "U": 0x18,
    "V": 0x19,
    "W": 0x1A,
    "X": 0x1B,
    "Y": 0x1C,
    "Z": 0x1D,
    "1": 0x1E,
    "2": 0x1F,
    "3": 0x20,
    "4": 0x21,
    "5": 0x22,
    "6": 0x23,
    "7": 0x24,
    "8": 0x25,
    "9": 0x26,
    "0": 0x27,
    "ENTER": 0x28,
    "RETURN": 0x28,
    "ESC": 0x29,
    "ESCAPE": 0x29,
    "BACKSPACE": 0x2A,
    "TAB": 0x2B,
    "SPACE": 0x2C,
    "F1": 0x3A,
    "F2": 0x3B,
    "F3": 0x3C,
    "F4": 0x3D,
    "F5": 0x3E,
    "F6": 0x3F,
    "F7": 0x40,
    "F8": 0x41,
    "F9": 0x42,
    "F10": 0x43,
    "F11": 0x44,
    "F12": 0x45,
}


def _get_bt_config() -> tuple[str, str]:
    with db() as connection:
        name_row = connection.execute(
            "SELECT value FROM settings WHERE key='btDeviceName'"
        ).fetchone()
        mac_row = connection.execute(
            "SELECT value FROM settings WHERE key='btTargetMac'"
        ).fetchone()
    device_name = (name_row["value"] if name_row else None) or os.getenv(
        "BT_KEYBOARD_NAME", "Pi4-BT-Keyboard"
    )
    target_mac = (mac_row["value"] if mac_row else None) or os.getenv(
        "BT_TARGET_MAC", ""
    )
    return device_name.strip(), target_mac.strip().upper()


def _detect_connected_bt_mac(configured_mac: str) -> str | None:
    if configured_mac:
        return configured_mac
    try:
        out = subprocess.check_output(
            ["bluetoothctl", "devices", "Connected"], text=True, timeout=2
        )
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and len(parts[1]) == 17:
                return parts[1].upper()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _get_hid_socket(target_mac: str) -> socket.socket:
    global _hid_interrupt_sock, _connected_mac
    if _hid_interrupt_sock is not None and _connected_mac == target_mac:
        return _hid_interrupt_sock

    if _hid_interrupt_sock is not None:
        try:
            _hid_interrupt_sock.close()
        except OSError:
            pass
        _hid_interrupt_sock = None

    # Linux L2CAP Socket: (MAC-Adresse, PSM)
    sock = socket.socket(
        socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, getattr(socket, "BTPROTO_L2CAP", 6)
    )
    sock.settimeout(2.0)
    sock.connect((target_mac, L2CAP_PSM_HID_INTERRUPT))
    _hid_interrupt_sock = sock
    _connected_mac = target_mac
    return sock


def _send_hid_key(modifier: int, keycode: int) -> None:
    global _hid_interrupt_sock
    _, configured_mac = _get_bt_config()
    target_mac = _detect_connected_bt_mac(configured_mac)
    if not target_mac:
        raise RuntimeError("Kein gekoppeltes/verbundenes Bluetooth-Zielgerät gefunden")

    # Bluetooth HID Report (0xA1 = INPUT Report, 0x01 = Report ID, danach 8-Byte Boot Keyboard Report)
    press_report = bytes(
        [0xA1, 0x01, modifier, 0x00, keycode, 0x00, 0x00, 0x00, 0x00, 0x00]
    )
    release_report = bytes([0xA1, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    try:
        sock = _get_hid_socket(target_mac)
        sock.sendall(press_report)
        sock.sendall(release_report)
    except OSError:
        if _hid_interrupt_sock is not None:
            try:
                _hid_interrupt_sock.close()
            except OSError:
                pass
            _hid_interrupt_sock = None
        sock = _get_hid_socket(target_mac)
        sock.sendall(press_report)
        sock.sendall(release_report)


def _send_bt_command(command: dict[str, Any]) -> None:
    cmd_type = command.get("type")

    if cmd_type == "shortcut":
        raw_keys = [
            str(k).strip().upper() for k in command.get("keys", []) if str(k).strip()
        ]
        modifier = 0
        keycode = 0
        for key in raw_keys:
            if key in HID_MODIFIERS:
                modifier |= HID_MODIFIERS[key]
            elif key in HID_KEYCODES and keycode == 0:
                keycode = HID_KEYCODES[key]
        if keycode == 0 and modifier == 0:
            raise ValueError("Keine gültige Taste für Shortcut angegeben")
        _send_hid_key(modifier, keycode)

    elif cmd_type == "text":
        text = str(command.get("text", ""))
        for ch in text:
            if ch == "\n":
                _send_hid_key(0, HID_KEYCODES["ENTER"])
            elif ch == " ":
                _send_hid_key(0, HID_KEYCODES["SPACE"])
            else:
                upper = ch.upper()
                if upper in HID_KEYCODES:
                    mod = HID_MODIFIERS["SHIFT"] if ch.isupper() else 0
                    _send_hid_key(mod, HID_KEYCODES[upper])


# --- API-Endpunkte ---


@app.get("/api/pico/status")
def device_status() -> dict[str, Any]:
    device_name, configured_mac = _get_bt_config()
    target_mac = _detect_connected_bt_mac(configured_mac)
    led_ready = PixelStrip is not None
    bt_ready = hasattr(socket, "AF_BLUETOOTH") and target_mac is not None
    return {
        "connected": bt_ready or led_ready,
        "bluetooth_target": target_mac,
        "device_name": device_name,
        "led_driver_ready": led_ready,
        "message": (
            "Bluetooth-Tastatur & LED bereit"
            if (bt_ready and led_ready)
            else "Bluetooth-Ziel oder LED-Treiber prüfen"
        ),
    }


@app.get("/api/pico/config")
def get_device_config() -> dict[str, Any]:
    device_name, target_mac = _get_bt_config()
    return {
        "deviceName": device_name,
        "targetMac": target_mac,
        "ledCount": LED_COUNT,
        "ledPin": LED_PIN,
    }


@app.put("/api/pico/config")
def set_device_config(body: dict[str, Any]) -> dict[str, Any]:
    device_name = (
        str(body.get("deviceName", "Pi4-BT-Keyboard")).strip()[:40] or "Pi4-BT-Keyboard"
    )
    target_mac = str(body.get("targetMac", "")).strip().upper()
    with db() as connection:
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('btDeviceName',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (device_name,),
        )
        connection.execute(
            "INSERT INTO settings(key,value) VALUES('btTargetMac',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (target_mac,),
        )
    return {"deviceName": device_name, "targetMac": target_mac}


@app.get("/api/pico/macros")
def get_macros() -> dict[str, Any]:
    with db() as connection:
        rows = connection.execute(
            "SELECT id,name,kind,payload,sort_order FROM pico_macros ORDER BY sort_order,id"
        ).fetchall()
    items = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "payload": payload,
            }
        )
    return {"items": items}


@app.put("/api/pico/macros")
def save_macros(body: PicoMacroConfig) -> dict[str, Any]:
    ids_seen: set[str] = set()
    with db() as connection:
        existing_ids = {
            row["id"]
            for row in connection.execute("SELECT id FROM pico_macros").fetchall()
        }
        for index, macro in enumerate(body.macros):
            macro_id = macro.id.strip() or f"macro-{index + 1}"
            name = macro.name.strip()[:40] or "Unbenanntes Makro"
            kind = (
                macro.kind if macro.kind in {"shortcut", "text", "led"} else "shortcut"
            )
            ids_seen.add(macro_id)
            connection.execute(
                "INSERT INTO pico_macros(id,name,kind,payload,sort_order) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,payload=excluded.payload,sort_order=excluded.sort_order",
                (macro_id, name, kind, json.dumps(macro.payload), index),
            )
        for old_id in existing_ids - ids_seen:
            connection.execute("DELETE FROM pico_macros WHERE id=?", (old_id,))
    return {"status": "saved", "count": len(ids_seen)}


@app.post("/api/pico/macros/{macro_id}/send")
def send_macro(macro_id: str) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute(
            "SELECT id,name,kind,payload FROM pico_macros WHERE id=?", (macro_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Makro nicht gefunden")

    try:
        payload = json.loads(row["payload"])
        if row["kind"] == "text":
            command = {"type": "text", "text": str(payload.get("text", ""))[:500]}
            _send_bt_command(command)
        elif row["kind"] == "led":
            command = _build_led_command(payload)
            _apply_led_command(command)
        else:
            keys = [
                str(key).strip().upper()
                for key in payload.get("keys", [])
                if str(key).strip()
            ][:8]
            command = {"type": "shortcut", "keys": keys}
            _send_bt_command(command)

        return {"status": "sent", "macro": row["name"]}
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503, detail=f"Bluetooth-/LED-Ausgabe fehlgeschlagen: {exc}"
        )


@app.post("/api/pico/led")
def send_led(body: PicoLedControl) -> dict[str, Any]:
    mode = body.mode.strip().lower()
    payload: dict[str, Any] = {
        "mode": mode,
        "color": body.color,
        "count": body.count,
        "brightness": body.brightness,
    }
    command = _build_led_command(payload)
    try:
        _apply_led_command(command)
        return {"status": "sent", "mode": command.get("mode", "fill")}
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503, detail=f"LED-Steuerung fehlgeschlagen: {exc}"
        )


@app.get("/api/weather")
async def get_weather() -> dict[str, Any]:
    import json
    from datetime import datetime, timezone

    with db() as connection:
        key_row = connection.execute(
            "SELECT value FROM settings WHERE key='weatherApiKey'"
        ).fetchone()
        city_row = connection.execute(
            "SELECT value FROM settings WHERE key='weatherCity'"
        ).fetchone()

    key = (
        key_row["value"] if key_row else os.getenv("OPENWEATHER_API_KEY", "")
    ).strip()
    city = (
        city_row["value"] if city_row else os.getenv("OPENWEATHER_CITY", "Berlin")
    ).strip() or "Berlin"

    with db() as connection:
        cached = connection.execute(
            "SELECT payload, synced_at FROM notion_cache WHERE kind='weather'"
        ).fetchone()

    if not key:
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {
            "status": "missing",
            "temperature": None,
            "condition": "Wetter nicht konfiguriert",
            "icon": "unknown",
            "city": city,
        }

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
            "condition": (
                data["weather"][0]["description"].capitalize()
                if data.get("weather")
                else "Unbekannt"
            ),
            "icon": data["weather"][0]["icon"] if data.get("weather") else "unknown",
            "city": data.get("name", city),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        with db() as connection:
            connection.execute(
                "INSERT INTO notion_cache(kind,payload,synced_at) VALUES('weather',?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload,synced_at=excluded.synced_at",
                (json.dumps(result), result["synced_at"]),
            )
        return result
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return {
                "status": "error",
                "temperature": None,
                "condition": "OpenWeather API-Key ungültig",
                "icon": "unknown",
                "city": city,
            }
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {
            "status": "error",
            "temperature": None,
            "condition": "Wetterdaten nicht erreichbar",
            "icon": "unknown",
            "city": city,
        }
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        if cached:
            cached_data = json.loads(cached["payload"])
            cached_data["status"] = "offline"
            return cached_data
        return {
            "status": "error",
            "temperature": None,
            "condition": "Wetterdaten nicht erreichbar",
            "icon": "unknown",
            "city": city,
        }


@app.put("/api/weather/config")
def set_weather_config(body: dict[str, str]) -> dict[str, str]:
    key = body.get("apiKey", "").strip()
    city = body.get("city", "").strip()
    with db() as connection:
        if key:
            connection.execute(
                "INSERT INTO settings(key,value) VALUES('weatherApiKey',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key,),
            )
        if city:
            connection.execute(
                "INSERT INTO settings(key,value) VALUES('weatherCity',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (city,),
            )
    return {
        "status": "saved",
        "configured": bool(key or os.getenv("OPENWEATHER_API_KEY", "")),
        "city": city,
    }


@app.get("/api/settings")
def get_settings() -> dict[str, str]:
    with db() as connection:
        rows = connection.execute("SELECT key,value FROM settings").fetchall()
    return {
        row["key"]: row["value"]
        for row in rows
        if row["key"] not in {"weatherApiKey", "notionApiKey", "icloudAppPassword"}
    }


@app.put("/api/settings/{key}")
def set_setting(key: str, value: dict[str, str]) -> dict[str, str]:
    if not value.get("value"):
        raise HTTPException(status_code=400, detail="Wert fehlt")
    with db() as connection:
        connection.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value["value"]),
        )
    return {"key": key, "value": value["value"]}


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
