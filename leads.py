import os
import re
import json
import httpx
import asyncio
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("AMELIA_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("AMELIA_TELEGRAM_CHAT_ID", "")

_conn = None
_conn_lock = asyncio.Lock()


async def _get_conn():
    global _conn
    if _conn is None:
        async with _conn_lock:
            if _conn is None:
                _conn = await asyncio.to_thread(
                    psycopg2.connect, DATABASE_URL, connect_timeout=10
                )
                _conn.autocommit = True
    return _conn


async def init_leads_db():
    if not DATABASE_URL:
        return
    try:
        conn = await _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                nombre TEXT,
                empresa TEXT,
                cargo TEXT,
                whatsapp TEXT,
                correo TEXT,
                mensaje_original TEXT,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                notified INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_ts ON leads(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_session ON leads(session_id)")
        cur.close()
    except Exception:
        pass


def _extract_lead_data(text: str) -> dict:
    """Extract lead contact data from a user message using regex patterns."""
    lead = {}

    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        lead["correo"] = email_match.group(0).strip().rstrip('.').rstrip(',')

    # WhatsApp / phone
    phone_match = re.search(
        r'\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{2,4}[\s-]?\d{2,4}|\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\d{10,12}',
        text
    )
    if phone_match:
        lead["whatsapp"] = phone_match.group(0).strip()

    # Name
    name_match = re.search(
        r'(?:me llamo|soy|mi nombre es|nombre:?\s*)[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
        text, re.IGNORECASE
    )
    if name_match:
        lead["nombre"] = name_match.group(1).strip()

    # Company
    comp_match = re.search(
        r'(?:empresa|compañía|trabajo en|de la empresa)\s+[:\s]*"?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s&.-]{2,40})"?',
        text, re.IGNORECASE
    )
    if comp_match:
        lead["empresa"] = comp_match.group(1).strip().rstrip('.').rstrip(',')

    # Cargo
    role_match = re.search(
        r'(?:cargo|puesto|rol)[:\s]*:?\s*([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{3,40})',
        text, re.IGNORECASE
    )
    if not role_match:
        role_match = re.search(
            r'soy (?:el |la )?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{3,40})',
            text, re.IGNORECASE
        )
    if not role_match:
        role_match = re.search(
            r'(?:gerente|director|coordinador|jefe|analista|presidente|ceo|cto|cfo|founder|fundador)[a-záéíóúñ]*\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{2,40})?',
            text, re.IGNORECASE
        )
    if role_match:
        role_text = role_match.group(0).strip().rstrip('.').rstrip(',')
        role_text = re.sub(r'^(soy el |soy la |soy )', '', role_text, flags=re.IGNORECASE)
        lead["cargo"] = role_text

    if len(lead) >= 2:
        return lead
    return {}


async def save_lead(session_id: str, text: str) -> dict | None:
    """Extract and save lead data. Returns the lead if captured."""
    if not DATABASE_URL:
        return None

    data = _extract_lead_data(text)
    if not data:
        return None

    try:
        conn = await _get_conn()
        cur = conn.cursor()

        cur.execute("SELECT id FROM leads WHERE session_id = %s", (session_id,))
        existing = cur.fetchone()

        if existing:
            sets = []
            vals = []
            for k, v in data.items():
                if v:
                    sets.append(f"{k} = %s")
                    vals.append(v)
            if sets:
                vals.append(session_id)
                cur.execute(f"UPDATE leads SET {', '.join(sets)} WHERE session_id = %s", vals)
        else:
            now = datetime.now(timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO leads (session_id, nombre, empresa, cargo, whatsapp, correo, mensaje_original, timestamp) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (session_id, data.get("nombre"), data.get("empresa"), data.get("cargo"),
                 data.get("whatsapp"), data.get("correo"), text[:500], now)
            )
        cur.close()
    except Exception:
        return None

    return data


async def notify_amelia(lead: dict, session_id: str, user_message: str):
    """Notify Amelia about a new lead via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    if TELEGRAM_CHAT_ID == "PLACEHOLDER":
        return

    nombre = lead.get("nombre", "Sin nombre")
    empresa = lead.get("empresa", "Sin empresa")
    cargo = lead.get("cargo", "Sin cargo")
    whatsapp = lead.get("whatsapp", "No proporcionado")
    correo = lead.get("correo", "No proporcionado")

    message = (
        f"🆕 *Nuevo lead capturado por M.A.T.I.A.S.*\n\n"
        f"👤 *Nombre:* {nombre}\n"
        f"🏢 *Empresa:* {empresa}\n"
        f"💼 *Cargo:* {cargo}\n"
        f"📱 *WhatsApp:* {whatsapp}\n"
        f"📧 *Correo:* {correo}\n\n"
        f"💬 *Mensaje:* {user_message[:200]}\n\n"
        f"🔗 Session: `{session_id[:12]}...`"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
    except Exception:
        pass


async def get_all_leads(limit: int = 50):
    if not DATABASE_URL:
        return []
    try:
        conn = await _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM leads ORDER BY timestamp DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        return [dict(row) for row in rows]
    except Exception:
        return []


async def get_lead_count():
    if not DATABASE_URL:
        return 0
    try:
        conn = await _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads")
        count = cur.fetchone()[0]
        cur.close()
        return count
    except Exception:
        return 0
