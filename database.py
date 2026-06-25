import os
import asyncio
import aiosqlite
import asyncpg
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = os.getenv("SQLITE_PATH", str(Path(__file__).resolve().parent / "data" / "matias_chat.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Supabase connection parts (evita problemas de URL encoding)
SUPABASE_HOST = os.getenv("SUPABASE_HOST", "")
SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "")
SUPABASE_PORT = os.getenv("SUPABASE_PORT", "6543")
SUPABASE_DB = os.getenv("SUPABASE_DB", "postgres")

_pg_pool = None
_pg_lock = asyncio.Lock()

# ── PostgreSQL connection ────────────────────────────────────────────

def _build_dsn():
    """Construye DSN sin errores de encoding en URL."""
    if SUPABASE_HOST and SUPABASE_PASSWORD:
        from urllib.parse import quote_plus
        return (
            f"postgresql://{SUPABASE_USER}:{quote_plus(SUPABASE_PASSWORD)}"
            f"@{SUPABASE_HOST}:{SUPABASE_PORT}/{SUPABASE_DB}"
        )
    return DATABASE_URL


async def _get_pg_pool():
    global _pg_pool
    dsn = _build_dsn()
    if _pg_pool is None and dsn:
        async with _pg_lock:
            if _pg_pool is None:
                _pg_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, ssl="require")
    return _pg_pool


async def _init_pg():
    """Crea tablas de chat en PostgreSQL si no existen."""
    pool = await _get_pg_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_interactions_session ON chat_interactions(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_interactions_timestamp ON chat_interactions(timestamp)")

        # Tabla de eventos de presentación
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS presentation_events (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('question', 'slide_view', 'slide_duration')),
                slide INTEGER,
                data JSONB DEFAULT '{}',
                ip TEXT,
                user_agent TEXT,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pe_session ON presentation_events(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pe_type ON presentation_events(event_type)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pe_timestamp ON presentation_events(timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pe_slide ON presentation_events(slide)")


# ── SQLite fallback (local dev) ──────────────────────────────────────

async def _get_sqlite():
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    return db


async def _init_sqlite():
    db = await _get_sqlite()
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
        # ── Analytics tables ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                url TEXT NOT NULL,
                referrer TEXT,
                timestamp TEXT NOT NULL,
                device_type TEXT DEFAULT 'unknown',
                browser TEXT DEFAULT 'unknown',
                os TEXT DEFAULT 'unknown',
                country TEXT DEFAULT 'unknown',
                source TEXT DEFAULT 'web',
                ip TEXT DEFAULT ''
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
                metadata TEXT,
                ip TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                session_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                page_views INTEGER DEFAULT 0,
                events INTEGER DEFAULT 0,
                device_type TEXT DEFAULT 'unknown',
                browser TEXT DEFAULT 'unknown',
                os TEXT DEFAULT 'unknown',
                country TEXT DEFAULT 'unknown',
                ip TEXT DEFAULT ''
            )
        """)
        # Migración: agregar columna ip si no existe (tablas ya creadas)
        for table in ('page_views', 'analytics_events', 'analytics_sessions'):
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN ip TEXT DEFAULT ''")
            except Exception:
                pass  # columna ya existe
        # ────────────────────────────────────────────────────────────────
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_session ON chat_interactions(session_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON chat_interactions(timestamp)")
        await db.commit()
    finally:
        await db.close()


# ── Public init ──────────────────────────────────────────────────────

async def init_db():
    if DATABASE_URL:
        await _init_pg()
    else:
        await _init_sqlite()


# ── Chat operations ──────────────────────────────────────────────────

async def log_interaction(session_id: str, role: str, content: str, model: str = None, source: str = "web"):
    try:
        now = datetime.now(timezone.utc)
        pool = await _get_pg_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO chat_interactions (session_id, role, content, timestamp, model, source) VALUES ($1, $2, $3, $4, $5, $6)",
                    session_id, role, content, now, model, source
                )
                await conn.execute("""
                    INSERT INTO chat_sessions (session_id, created_at, last_activity, message_count)
                    VALUES ($1, $2, $2, 1)
                    ON CONFLICT (session_id) DO UPDATE SET
                        last_activity = $2,
                        message_count = chat_sessions.message_count + 1
                """, session_id, now)
            return
        # SQLite fallback
        db = await _get_sqlite()
        try:
            now_str = now.isoformat()
            await db.execute(
                "INSERT INTO chat_interactions (session_id, role, content, timestamp, model, source) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, now_str, model, source)
            )
            await db.execute("""
                INSERT INTO chat_sessions (session_id, created_at, last_activity, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_activity = excluded.last_activity,
                    message_count = message_count + 1
            """, (session_id, now_str, now_str))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def get_recent_interactions(limit: int = 50):
    pool = await _get_pg_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM chat_interactions ORDER BY timestamp DESC LIMIT $1", limit
            )
            return [dict(row) for row in rows]
    # SQLite fallback
    db = await _get_sqlite()
    try:
        cursor = await db.execute("SELECT * FROM chat_interactions ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_sessions(limit: int = 50):
    pool = await _get_pg_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT session_id, created_at, last_activity, message_count FROM chat_sessions ORDER BY last_activity DESC LIMIT $1", limit
            )
            return [dict(row) for row in rows]
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT session_id, created_at, last_activity, message_count FROM chat_sessions ORDER BY last_activity DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_total_count():
    pool = await _get_pg_pool()
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM chat_interactions")
            return row["count"]
    db = await _get_sqlite()
    try:
        cursor = await db.execute("SELECT COUNT(*) as count FROM chat_interactions")
        row = await cursor.fetchone()
        return dict(row)["count"]
    finally:
        await db.close()


async def get_session_interactions(session_id: str, limit: int = 50):
    pool = await _get_pg_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM chat_interactions WHERE session_id = $1 ORDER BY timestamp DESC LIMIT $2",
                session_id, limit
            )
            return [dict(row) for row in rows]
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT * FROM chat_interactions WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ── Analytics (SQLite local, datos no criticos) ──────────────────────

import hashlib

def _detect_device(ua: str) -> tuple:
    ua_lower = ua.lower() if ua else ""
    device, browser, os_name = "desktop", "other", "other"
    if "iphone" in ua_lower or "ipad" in ua_lower or "ipod" in ua_lower:
        device = "mobile" if "iphone" in ua_lower or "ipod" in ua_lower else "tablet"
    elif "android" in ua_lower:
        device = "tablet" if "tablet" in ua_lower else "mobile"
    if "edg/" in ua_lower: browser = "edge"
    elif "chrome/" in ua_lower: browser = "chrome"
    elif "safari/" in ua_lower: browser = "safari"
    elif "firefox/" in ua_lower: browser = "firefox"
    if "iphone" in ua_lower or "ipad" in ua_lower: os_name = "ios"
    elif "macintosh" in ua_lower or "mac os" in ua_lower: os_name = "macos"
    elif "android" in ua_lower: os_name = "android"
    elif "windows" in ua_lower: os_name = "windows"
    elif "linux" in ua_lower: os_name = "linux"
    return device, browser, os_name


async def log_page_view(session_id, url, referrer, user_agent, country, source="web", ip=""):
    try:
        device, browser, os_name = _detect_device(user_agent)
        db = await _get_sqlite()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO page_views (session_id, url, referrer, timestamp, device_type, browser, os, country, source, ip) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (session_id, url, referrer, now, device, browser, os_name, country, source, ip)
            )
            await db.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country, ip)
                VALUES (?,?,?,1,0,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET
                last_seen=excluded.last_seen, page_views=page_views+1, device_type=excluded.device_type, browser=excluded.browser, os=excluded.os, country=excluded.country, ip=excluded.ip
            """, (session_id, now, now, device, browser, os_name, country, ip))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def log_event(session_id, event_type, element, url, metadata=None, ip=""):
    try:
        db = await _get_sqlite()
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO analytics_events (session_id, event_type, element, url, timestamp, metadata, ip) VALUES (?,?,?,?,?,?,?)",
                (session_id, event_type, element, url, now, metadata, ip)
            )
            await db.execute("""
                INSERT INTO analytics_sessions (session_id, first_seen, last_seen, page_views, events, device_type, browser, os, country)
                VALUES (?,?,?,0,1,'unknown','unknown','unknown','unknown') ON CONFLICT(session_id) DO UPDATE SET
                last_seen=excluded.last_seen, events=events+1
            """, (session_id, now, now))
            await db.commit()
        finally:
            await db.close()
    except Exception:
        pass


async def get_analytics_dashboard():
    db = await _get_sqlite()
    try:
        c = await db.execute("SELECT COUNT(*) as c FROM page_views")
        total_pageviews = dict(await c.fetchone())["c"]
        c = await db.execute("SELECT COUNT(DISTINCT session_id) as c FROM page_views")
        total_visitors = dict(await c.fetchone())["c"]
        return {"total_pageviews": total_pageviews, "total_visitors": total_visitors}
    finally:
        await db.close()


# ── Presentation events ───────────────────────────────────────────────

async def log_presentation_event(session_id: str, event_type: str, slide: int = None,
                                  data: dict = None, ip: str = None, user_agent: str = None):
    """Registra un evento de la presentación en PostgreSQL."""
    pool = await _get_pg_pool()
    if pool:
        try:
            import json as _json
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO presentation_events (session_id, event_type, slide, data, ip, user_agent)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    session_id, event_type, slide,
                    _json.dumps(data or {}), ip, user_agent
                )
        except Exception:
            pass


async def get_presentation_stats(days: int = 7):
    """Estadísticas de la presentación para Amelia. PostgreSQL."""
    pool = await _get_pg_pool()
    if not pool:
        return {"error": "No PostgreSQL connection"}
    
    async with pool.acquire() as conn:
        # Total preguntas
        q_row = await conn.fetchrow(
            """SELECT COUNT(*) as c FROM presentation_events
               WHERE event_type='question' AND timestamp > NOW() - $1::interval""",
            f"{days} days"
        )
        total_questions = q_row["c"]
        
        # Sesiones únicas
        s_row = await conn.fetchrow(
            """SELECT COUNT(DISTINCT session_id) as c FROM presentation_events
               WHERE timestamp > NOW() - $1::interval""",
            f"{days} days"
        )
        unique_sessions = s_row["c"]
        
        # Preguntas por slide
        qs_rows = await conn.fetch(
            """SELECT slide, COUNT(*) as c, 
                      COUNT(DISTINCT session_id) as sessions
               FROM presentation_events
               WHERE event_type='question' AND timestamp > NOW() - $1::interval AND slide IS NOT NULL
               GROUP BY slide ORDER BY c DESC""",
            f"{days} days"
        )
        questions_by_slide = [{"slide": r["slide"], "count": r["c"], "sessions": r["sessions"]} for r in qs_rows]
        
        # Promedio de preguntas por sesión
        avg_q = round(total_questions / unique_sessions, 1) if unique_sessions > 0 else 0
        
        # Tiempo promedio por slide (slide_duration events)
        dur_rows = await conn.fetch(
            """SELECT slide, 
                      COUNT(*) as views,
                      ROUND(AVG((data->>'seconds')::numeric), 0) as avg_seconds
               FROM presentation_events
               WHERE event_type='slide_duration' AND timestamp > NOW() - $1::interval AND slide IS NOT NULL
               GROUP BY slide ORDER BY avg_seconds DESC""",
            f"{days} days"
        )
        duration_by_slide = [{"slide": r["slide"], "views": r["views"], "avg_seconds": int(r["avg_seconds"])} for r in dur_rows]
        
        # Últimas preguntas
        last_rows = await conn.fetch(
            """SELECT session_id, slide, data->>'question' as question, 
                      data->>'reply' as reply, timestamp
               FROM presentation_events
               WHERE event_type='question' AND timestamp > NOW() - $1::interval
               ORDER BY timestamp DESC LIMIT 10""",
            f"{days} days"
        )
        recent_questions = [
            {"session_id": r["session_id"], "slide": r["slide"],
             "question": r["question"][:200] if r["question"] else "",
             "reply": r["reply"][:200] if r["reply"] else "",
             "timestamp": r["timestamp"].isoformat()}
            for r in last_rows
        ]
        
        # Sesiones que hicieron preguntas hoy
        today_rows = await conn.fetch(
            """SELECT COUNT(DISTINCT session_id) as c FROM presentation_events
               WHERE event_type='question' AND timestamp > CURRENT_DATE""",
        )
        questions_today = today_rows[0]["c"]
        
        # Sesiones con interaccion hoy (cualquier evento)
        active_rows = await conn.fetch(
            """SELECT COUNT(DISTINCT session_id) as c FROM presentation_events
               WHERE timestamp > CURRENT_DATE""",
        )
        active_today = active_rows[0]["c"]
        
        return {
            "period_days": days,
            "total_questions": total_questions,
            "unique_sessions": unique_sessions,
            "avg_questions_per_session": avg_q,
            "active_sessions_today": active_today,
            "questions_today": questions_today,
            "questions_by_slide": questions_by_slide,
            "duration_by_slide": duration_by_slide,
            "recent_questions": recent_questions,
        }


async def get_recent_pageviews(limit=50):
    db = await _get_sqlite()
    try:
        cursor = await db.execute("SELECT * FROM page_views ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_visitor_sessions(limit=50):
    db = await _get_sqlite()
    try:
        cursor = await db.execute("SELECT * FROM analytics_sessions ORDER BY last_seen DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_page_views_by_session(session_id: str) -> list[dict]:
    """Todas las page_views de una sesión."""
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT * FROM page_views WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_events_by_session(session_id: str) -> list[dict]:
    """Todos los analytics_events de una sesión."""
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT * FROM analytics_events WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_sessions_by_ip(ip: str) -> list[dict]:
    """Todas las sessions de una IP."""
    if not ip:
        return []
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT * FROM analytics_sessions WHERE ip = ? ORDER BY last_seen DESC",
            (ip,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_page_views_by_ip(ip: str) -> list[dict]:
    """Todas las page_views de una IP."""
    if not ip:
        return []
    db = await _get_sqlite()
    try:
        cursor = await db.execute(
            "SELECT * FROM page_views WHERE ip = ? ORDER BY timestamp DESC",
            (ip,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
