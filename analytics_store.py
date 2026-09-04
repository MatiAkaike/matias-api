"""Analítica persistente del agente web M.A.T.I.A.S. en PostgreSQL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import database


async def init_analytics_db() -> None:
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no está configurado para analítica")
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                path TEXT,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        migrations = [
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS url TEXT",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS referrer TEXT DEFAULT ''",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS user_agent TEXT DEFAULT ''",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS device_type TEXT DEFAULT 'unknown'",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS browser TEXT DEFAULT 'unknown'",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS os TEXT DEFAULT 'unknown'",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'unknown'",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'web'",
            "ALTER TABLE page_views ADD COLUMN IF NOT EXISTS ip TEXT DEFAULT ''",
        ]
        for statement in migrations:
            await conn.execute(statement)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_events (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                element TEXT DEFAULT '',
                url TEXT DEFAULT '',
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                metadata JSONB DEFAULT '{}'::jsonb,
                ip TEXT DEFAULT ''
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                first_seen TIMESTAMPTZ DEFAULT NOW(),
                last_seen TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        for statement in [
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS page_views INTEGER DEFAULT 0",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS events INTEGER DEFAULT 0",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS device_type TEXT DEFAULT 'unknown'",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS browser TEXT DEFAULT 'unknown'",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS os TEXT DEFAULT 'unknown'",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS country TEXT DEFAULT 'unknown'",
            "ALTER TABLE analytics_sessions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'web'",
        ]:
            await conn.execute(statement)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_page_views_session ON page_views(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_page_views_timestamp ON page_views(timestamp DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_session ON analytics_events(session_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_timestamp ON analytics_events(timestamp DESC)")
        try:
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_analytics_sessions_session ON analytics_sessions(session_id) WHERE session_id IS NOT NULL"
            )
        except Exception:
            # Una instalación antigua puede tener sesiones repetidas; no se borran automáticamente.
            pass


def _detect_device(user_agent: str) -> tuple[str, str, str]:
    ua = (user_agent or "").lower()
    device = "desktop"
    if any(value in ua for value in ("iphone", "android", "mobile")):
        device = "mobile"
    elif "ipad" in ua or "tablet" in ua:
        device = "tablet"
    browser = "other"
    if "edg/" in ua:
        browser = "edge"
    elif "chrome/" in ua:
        browser = "chrome"
    elif "safari/" in ua:
        browser = "safari"
    elif "firefox/" in ua:
        browser = "firefox"
    os_name = "other"
    if "iphone" in ua or "ipad" in ua:
        os_name = "ios"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macos"
    elif "android" in ua:
        os_name = "android"
    elif "windows" in ua:
        os_name = "windows"
    elif "linux" in ua:
        os_name = "linux"
    return device, browser, os_name


async def _upsert_session(
    conn: Any,
    session_id: str,
    *,
    ip: str = "",
    user_agent: str = "",
    country: str = "unknown",
    source: str = "web",
    page_view_delta: int = 0,
    event_delta: int = 0,
) -> None:
    device, browser, os_name = _detect_device(user_agent)
    result = await conn.execute(
        """
        UPDATE analytics_sessions SET
            last_seen=NOW(), ip=COALESCE(NULLIF($2,''), ip),
            user_agent=COALESCE(NULLIF($3,''), user_agent), country=$4,
            source=$5, device_type=$6, browser=$7, os=$8,
            page_views=COALESCE(page_views,0)+$9,
            events=COALESCE(events,0)+$10
        WHERE session_id=$1
        """,
        session_id, ip, user_agent, country, source, device, browser, os_name,
        page_view_delta, event_delta,
    )
    if result.endswith("0"):
        await conn.execute(
            """
            INSERT INTO analytics_sessions (
                session_id, ip, user_agent, first_seen, last_seen, page_views, events,
                device_type, browser, os, country, source
            ) VALUES ($1,$2,$3,NOW(),NOW(),$4,$5,$6,$7,$8,$9,$10)
            """,
            session_id, ip, user_agent, page_view_delta, event_delta,
            device, browser, os_name, country, source,
        )


async def log_page_view(
    session_id: str,
    url: str,
    referrer: str,
    user_agent: str,
    country: str,
    source: str = "web",
    ip: str = "",
) -> None:
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no disponible para registrar pageview")
    device, browser, os_name = _detect_device(user_agent)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO page_views (
                    session_id, path, url, referrer, user_agent, timestamp,
                    device_type, browser, os, country, source, ip
                ) VALUES ($1,$2,$2,$3,$4,NOW(),$5,$6,$7,$8,$9,$10)
                """,
                session_id, url, referrer, user_agent, device, browser, os_name, country, source, ip,
            )
            await _upsert_session(
                conn, session_id, ip=ip, user_agent=user_agent, country=country,
                source=source, page_view_delta=1,
            )


async def log_event(
    session_id: str,
    event_type: str,
    element: str,
    url: str,
    metadata: str | None = None,
    ip: str = "",
) -> None:
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no disponible para registrar evento")
    parsed: dict[str, Any] = {}
    if metadata:
        try:
            value = json.loads(metadata)
            parsed = value if isinstance(value, dict) else {"value": value}
        except json.JSONDecodeError:
            parsed = {"value": metadata[:1000]}
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO analytics_events
                   (session_id,event_type,element,url,timestamp,metadata,ip)
                   VALUES ($1,$2,$3,$4,NOW(),$5::jsonb,$6)""",
                session_id, event_type, element, url, json.dumps(parsed, ensure_ascii=False), ip,
            )
            await _upsert_session(conn, session_id, ip=ip, event_delta=1)


def _serialize(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = dict(row)
        for key, value in list(item.items()):
            if hasattr(value, "isoformat"):
                item[key] = value.isoformat()
        result.append(item)
    return result


async def get_analytics_dashboard() -> dict[str, Any]:
    pool = await database._get_pg_pool()
    if not pool:
        return {"database": "unavailable"}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM page_views) total_pageviews,
                (SELECT COUNT(DISTINCT session_id) FROM page_views) total_visitors,
                (SELECT COUNT(*) FROM analytics_events) total_events,
                (SELECT COUNT(*) FROM leads) total_leads,
                (SELECT COUNT(*) FROM chat_interactions) total_interactions,
                (SELECT COUNT(*) FROM page_views WHERE timestamp >= CURRENT_DATE) pageviews_today,
                (SELECT COUNT(*) FROM leads WHERE created_at >= CURRENT_DATE) leads_today
            """
        )
        return {"database": "postgresql", **dict(row)}


async def get_recent_pageviews(limit: int = 50) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM page_views ORDER BY timestamp DESC LIMIT $1", limit)
        return _serialize(rows)


async def get_visitor_sessions(limit: int = 50) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM analytics_sessions ORDER BY last_seen DESC LIMIT $1", limit)
        return _serialize(rows)


async def get_page_views_by_session(session_id: str) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM page_views WHERE session_id=$1 ORDER BY timestamp", session_id)
        return _serialize(rows)


async def get_events_by_session(session_id: str) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM analytics_events WHERE session_id=$1 ORDER BY timestamp", session_id)
        return _serialize(rows)


async def get_sessions_by_ip(ip: str) -> list[dict[str, Any]]:
    if not ip:
        return []
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM analytics_sessions WHERE ip=$1 ORDER BY last_seen DESC", ip)
        return _serialize(rows)


async def get_page_views_by_ip(ip: str) -> list[dict[str, Any]]:
    if not ip:
        return []
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM page_views WHERE ip=$1 ORDER BY timestamp DESC", ip)
        return _serialize(rows)


async def get_conversions(days: int = 7) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.session_id, e.timestamp, e.element, e.url,
                   s.ip, s.country, s.page_views AS pageviews_en_sesion
            FROM analytics_events e
            LEFT JOIN analytics_sessions s ON s.session_id=e.session_id
            WHERE e.event_type='demo_click' AND e.timestamp >= $1
            ORDER BY e.timestamp DESC
            """,
            since,
        )
        return _serialize(rows)
