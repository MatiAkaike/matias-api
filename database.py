import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
import hashlib

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg.AsyncConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=3,
            kwargs={"row_factory": dict_row}
        )
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_interactions (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                model TEXT,
                source TEXT DEFAULT 'web'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                message_count INTEGER DEFAULT 0
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_int_session ON chat_interactions(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_int_ts ON chat_interactions(timestamp)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                url TEXT NOT NULL,
                referrer TEXT,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                device_type TEXT,
                browser TEXT,
                os TEXT,
                country TEXT,
                source TEXT DEFAULT 'web'
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                element TEXT,
                url TEXT,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                metadata TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                session_id TEXT PRIMARY KEY,
                first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                page_views INTEGER DEFAULT 0,
                events INTEGER DEFAULT 0,
                device_type TEXT,
                browser TEXT,
                os TEXT,
                country TEXT
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_session ON page_views(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_ts ON page_views(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_ts ON analytics_events(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_type ON analytics_events(event_type)")


async def log_interaction(session_id: str, role: str, content: str, model: str = None, source: str = "web"):
    try:
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO chat_interactions (session_id, role, content, model, source) VALUES (%s, %s, %s, %s, %s)",
                (session_id, role, content, model, source)
            )
            await conn.execute("""
                INSERT INTO chat_sessions (session_id, created_at, last_activity, message_count)
                VALUES (%s, NOW(), NOW(), 1)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_activity = NOW(),
                    message_count = chat_sessions.message_count + 1
            """, (session_id,))
    except Exception:
        pass


async def get_recent_interactions(limit: int = 50):
    pool = await get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute("SELECT * FROM chat_interactions ORDER BY timestamp DESC LIMIT %s", (limit,))
        return [dict(row) for row in await rows.fetchall()]


async def get_sessions(limit: int = 50):
    pool = await get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute(
            "SELECT session_id, created_at, last_activity, message_count FROM chat_sessions ORDER BY last_activity DESC LIMIT %s",
            (limit,)
        )
        return [dict(row) for row in await rows.fetchall()]


async def get_total_count():
    pool = await get_pool()
    async with pool.connection() as conn:
        row = (await (await conn.execute("SELECT COUNT(*) as count FROM chat_interactions")).fetchone())
        return row["count"]


async def get_session_interactions(session_id: str, limit: int = 50):
    pool = await get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute(
            "SELECT * FROM chat_interactions WHERE session_id = %s ORDER BY timestamp DESC LIMIT %s",
            (session_id, limit)
        )
        return [dict(row) for row in await rows.fetchall()]


# ─── Analytics ────────────────────────────────────────────────────────────

def _detect_device(ua: str) -> tuple:
    ua_lower = ua.lower() if ua else ""
    device, browser, os_name = "desktop", "other", "other"

    if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        device = "mobile" if "iphone" in ua_lower or "ipod" in ua_lower else "tablet"
    elif "android" in ua_lower:
        device = "tablet" if "tablet" in ua_lower else "mobile"
    elif "macintosh" in ua_lower or "windows" in ua_lower or "linux" in ua_lower:
        device = "desktop"

    if "edg/" in ua_lower: browser = "edge"
    elif "chrome/" in ua_lower: browser = "chrome"
    elif "safari/" in ua_lower: browser = "safari"
    elif "firefox/" in ua_lower: browser = "firefox"

    if "iphone" in ua_lower or "ipad" in ua_lower: os_name = "ios"
    elif "macintosh" in ua_lower: os_name = "macos"
    elif "android" in ua_lower: os_name = "android"
    elif "windows" in ua_lower: os_name = "windows"
    elif "linux" in ua_lower: os_name = "linux"

    return device, browser, os_name


async def log_page_view(session_id: str, url: str, referrer: str, user_agent: str, country: str, source: str = "web"):
    try:
        device, browser, os_name = _detect_device(user_agent)
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO page_views (session_id, url, referrer, device_type, browser, os, country, source) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (session_id, url, referrer, device, browser, os_name, country, source)
            )
            await conn.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country)
                VALUES (%s, NOW(), NOW(), 1, 0, %s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = NOW(),
                    page_views = analytics_sessions.page_views + 1,
                    device_type = %s, browser = %s, os = %s, country = %s
            """, (session_id, device, browser, os_name, country, device, browser, os_name, country))
    except Exception:
        pass


async def log_event(session_id: str, event_type: str, element: str, url: str, metadata: str = None):
    try:
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO analytics_events (session_id, event_type, element, url, metadata) VALUES (%s, %s, %s, %s, %s)",
                (session_id, event_type, element, url, metadata)
            )
            await conn.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country)
                VALUES (%s, NOW(), NOW(), 0, 1, 'unknown', 'unknown', 'unknown', 'unknown')
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = NOW(),
                    events = analytics_sessions.events + 1
            """, (session_id,))
    except Exception:
        pass


async def get_analytics_dashboard():
    pool = await get_pool()
    async with pool.connection() as conn:
        total_pageviews = (await (await conn.execute("SELECT COUNT(*) FROM page_views")).fetchone())["count"]
        total_visitors = (await (await conn.execute("SELECT COUNT(DISTINCT session_id) FROM page_views")).fetchone())["count"]
        total_events = (await (await conn.execute("SELECT COUNT(*) FROM analytics_events WHERE event_type != 'page_view'")).fetchone())["count"]

        devices = {row["device_type"]: row["c"] for row in await (await conn.execute(
            "SELECT device_type, COUNT(*) as c FROM analytics_sessions GROUP BY device_type ORDER BY c DESC"
        )).fetchall()}

        browsers = {row["browser"]: row["c"] for row in await (await conn.execute(
            "SELECT browser, COUNT(*) as c FROM analytics_sessions GROUP BY browser ORDER BY c DESC LIMIT 5"
        )).fetchall()}

        countries = {row["country"]: row["c"] for row in await (await conn.execute(
            "SELECT country, COUNT(*) as c FROM analytics_sessions WHERE country != 'unknown' AND country != '' GROUP BY country ORDER BY c DESC LIMIT 10"
        )).fetchall()}

        hourly = {str(row["hour"]).zfill(2): row["c"] for row in await (await conn.execute(
            "SELECT EXTRACT(HOUR FROM timestamp)::int as hour, COUNT(*) as c FROM page_views GROUP BY hour ORDER BY hour"
        )).fetchall()}

        top_pages = {row["url"]: row["c"] for row in await (await conn.execute(
            "SELECT url, COUNT(*) as c FROM page_views GROUP BY url ORDER BY c DESC LIMIT 10"
        )).fetchall()}

        top_events = [{"event": row["event_type"], "element": row["element"], "count": row["c"]} for row in await (await conn.execute(
            "SELECT event_type, element, COUNT(*) as c FROM analytics_events WHERE event_type != 'page_view' GROUP BY event_type, element ORDER BY c DESC LIMIT 10"
        )).fetchall()]

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


async def get_recent_pageviews(limit: int = 50):
    pool = await get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute("SELECT * FROM page_views ORDER BY timestamp DESC LIMIT %s", (limit,))
        result = await rows.fetchall()
        return [dict(row) for row in result]


async def get_visitor_sessions(limit: int = 50):
    pool = await get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute("SELECT * FROM analytics_sessions ORDER BY last_seen DESC LIMIT %s", (limit,))
        result = await rows.fetchall()
        return [dict(row) for row in result]
