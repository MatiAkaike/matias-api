import os
import aiosqlite
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = os.getenv("SQLITE_PATH", str(Path(__file__).resolve().parent / "data" / "matias_chat.db"))


async def get_db():
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                model TEXT,
                source TEXT DEFAULT 'web'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                message_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON chat_interactions(session_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON chat_interactions(timestamp)")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                url TEXT NOT NULL,
                referrer TEXT,
                timestamp TEXT NOT NULL,
                device_type TEXT,
                browser TEXT,
                os TEXT,
                country TEXT,
                source TEXT DEFAULT 'web'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                element TEXT,
                url TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                session_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                page_views INTEGER DEFAULT 0,
                events INTEGER DEFAULT 0,
                device_type TEXT,
                browser TEXT,
                os TEXT,
                country TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pageviews_session ON page_views(session_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pageviews_timestamp ON page_views(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON analytics_events(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON analytics_events(event_type)")
        await db.commit()
    finally:
        await db.close()


async def log_interaction(session_id: str, role: str, content: str, model: str = None, source: str = "web"):
    try:
        db = await get_db()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO chat_interactions (session_id, role, content, timestamp, model, source) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, now, model, source)
            )
            await db.execute("""
                INSERT INTO chat_sessions (session_id, created_at, last_activity, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_activity = excluded.last_activity,
                    message_count = message_count + 1
            """, (session_id, now, now))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def get_recent_interactions(limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM chat_interactions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_sessions(limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT session_id, created_at, last_activity, message_count FROM chat_sessions ORDER BY last_activity DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_total_count():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as count FROM chat_interactions")
        row = await cursor.fetchone()
        return dict(row)["count"]
    finally:
        await db.close()


async def get_session_interactions(session_id: str, limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM chat_interactions WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ─── Analytics ────────────────────────────────────────────────────────────

import hashlib

def _detect_device(ua: str) -> tuple:
    ua_lower = ua.lower() if ua else ""
    device = "desktop"
    browser = "other"
    os_name = "other"

    if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        device = "mobile" if "iphone" in ua_lower or "ipod" in ua_lower else "tablet"
    elif "android" in ua_lower:
        device = "tablet" if "tablet" in ua_lower else "mobile"
    elif "macintosh" in ua_lower or "windows" in ua_lower or "linux" in ua_lower:
        device = "desktop"

    if "edg/" in ua_lower:
        browser = "edge"
    elif "chrome/" in ua_lower and "edg/" not in ua_lower:
        browser = "chrome"
    elif "safari/" in ua_lower and "chrome/" not in ua_lower:
        browser = "safari"
    elif "firefox/" in ua_lower:
        browser = "firefox"

    if "iphone" in ua_lower or "ipad" in ua_lower or "macintosh" in ua_lower:
        os_name = "ios" if "iphone" in ua_lower or "ipad" in ua_lower else "macos"
    elif "android" in ua_lower:
        os_name = "android"
    elif "windows" in ua_lower:
        os_name = "windows"
    elif "linux" in ua_lower and "android" not in ua_lower:
        os_name = "linux"

    return device, browser, os_name


async def log_page_view(session_id: str, url: str, referrer: str, user_agent: str, country: str, source: str = "web"):
    try:
        device, browser, os_name = _detect_device(user_agent)
        db = await get_db()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO page_views (session_id, url, referrer, timestamp, device_type, browser, os, country, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, url, referrer, now, device, browser, os_name, country, source)
            )
            await db.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country)
                VALUES (?, ?, ?, 1, 0, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    page_views = page_views + 1,
                    device_type = excluded.device_type,
                    browser = excluded.browser,
                    os = excluded.os,
                    country = excluded.country
            """, (session_id, now, now, device, browser, os_name, country))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def log_event(session_id: str, event_type: str, element: str, url: str, metadata: str = None):
    try:
        db = await get_db()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO analytics_events (session_id, event_type, element, url, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, event_type, element, url, now, metadata)
            )
            await db.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country)
                VALUES (?, ?, ?, 0, 1, 'unknown', 'unknown', 'unknown', 'unknown')
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    events = events + 1
            """, (session_id, now, now))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def get_analytics_dashboard():
    db = await get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()

        c = await db.execute("SELECT COUNT(*) as c FROM page_views")
        total_pageviews = dict(await c.fetchone())["c"]

        c = await db.execute("SELECT COUNT(DISTINCT session_id) as c FROM page_views")
        total_visitors = dict(await c.fetchone())["c"]

        c = await db.execute("SELECT COUNT(*) as c FROM analytics_events WHERE event_type != 'page_view'")
        total_events = dict(await c.fetchone())["c"]

        c = await db.execute("""
            SELECT device_type, COUNT(*) as c FROM analytics_sessions
            GROUP BY device_type ORDER BY c DESC
        """)
        devices = {row["device_type"]: row["c"] for row in await c.fetchall()}

        c = await db.execute("""
            SELECT browser, COUNT(*) as c FROM analytics_sessions
            GROUP BY browser ORDER BY c DESC LIMIT 5
        """)
        browsers = {row["browser"]: row["c"] for row in await c.fetchall()}

        c = await db.execute("""
            SELECT country, COUNT(*) as c FROM analytics_sessions
            WHERE country != 'unknown' AND country != ''
            GROUP BY country ORDER BY c DESC LIMIT 10
        """)
        countries = {row["country"]: row["c"] for row in await c.fetchall()}

        c = await db.execute("""
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as c
            FROM page_views GROUP BY hour ORDER BY hour
        """)
        hourly = {str(row["hour"]).zfill(2): row["c"] for row in await c.fetchall()}

        c = await db.execute("""
            SELECT url, COUNT(*) as c FROM page_views
            GROUP BY url ORDER BY c DESC LIMIT 10
        """)
        top_pages = {row["url"]: row["c"] for row in await c.fetchall()}

        c = await db.execute("""
            SELECT event_type, element, COUNT(*) as c FROM analytics_events
            WHERE event_type != 'page_view'
            GROUP BY event_type, element ORDER BY c DESC LIMIT 10
        """)
        top_events = [{"event": row["event_type"], "element": row["element"], "count": row["c"]} for row in await c.fetchall()]

        return {
            "total_pageviews": total_pageviews,
            "total_visitors": total_visitors,
            "total_events": total_events,
            "devices": devices,
            "browsers": browsers,
            "countries": countries,
            "hourly_distribution": hourly,
            "top_pages": top_pages,
            "top_events": top_events,
        }
    finally:
        await db.close()


async def get_recent_pageviews(limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM page_views ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_visitor_sessions(limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM analytics_sessions ORDER BY last_seen DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
