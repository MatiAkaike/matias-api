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
