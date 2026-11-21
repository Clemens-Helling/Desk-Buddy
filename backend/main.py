import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env", override=True)
DB_PATH = ROOT / "backend" / "deskbuddy.db"
FRONTEND_DIST = ROOT / "frontend" / "dist"

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


init_db()


def notion_headers() -> dict[str, str]:
    key = os.getenv("NOTION_API_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Notion ist nicht konfiguriert")
    return {"Authorization": f"Bearer {key}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "notion_configured": bool(os.getenv("NOTION_API_KEY")), "database": str(DB_PATH)}


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


@app.get("/api/calendar")
def calendar() -> dict[str, Any]:
    return {"items": [], "configured": bool(os.getenv("NOTION_CALENDAR_DATABASE_ID")), "synced_at": None}


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
    return {row["key"]: row["value"] for row in rows if row["key"] not in {"weatherApiKey", "notionApiKey"}}


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
