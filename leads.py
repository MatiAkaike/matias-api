import os
import re
import json
import httpx
import asyncio
from datetime import datetime, timezone

import aiosqlite
from pathlib import Path

DB_PATH = os.getenv("SQLITE_PATH", str(Path(__file__).resolve().parent / "data" / "matias_lead.db"))

TELEGRAM_BOT_TOKEN = os.getenv("AMELIA_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("AMELIA_TELEGRAM_CHAT_ID", "")


async def _get_db():
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    return db


async def init_leads_db():
    db = await _get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                nombre TEXT,
                empresa TEXT,
                cargo TEXT,
                whatsapp TEXT,
                correo TEXT,
                mensaje_original TEXT,
                timestamp TEXT NOT NULL,
                notified INTEGER DEFAULT 0
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_timestamp ON leads(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_session ON leads(session_id)")
        await db.commit()
    finally:
        await db.close()


def extract_lead_data(text: str) -> dict:
    """Extract lead contact data from a user message using regex patterns."""
    lead = {}

    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        lead["correo"] = email_match.group(0).strip().rstrip('.').rstrip(',')

    # WhatsApp / phone (various formats)
    phone_patterns = [
        r'\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{2,4}[\s-]?\d{2,4}',  # +57 320 475 6752
        r'\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}',               # 320 475 67 52
        r'\d{10,12}',                                                # 3204756752
    ]
    for pat in phone_patterns:
        phone_match = re.search(pat, text)
        if phone_match:
            lead["whatsapp"] = phone_match.group(0).strip()
            break

    # Name patterns: "Me llamo X", "Soy X", "Mi nombre es X", "nombre: X"
    name_patterns = [
        r'(?:me llamo|soy|mi nombre es|nombre:?\s*)[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
        r'(?:yo soy|me dicen)[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
    ]
    for pat in name_patterns:
        name_match = re.search(pat, text, re.IGNORECASE)
        if name_match:
            lead["nombre"] = name_match.group(1).strip()
            break

    # Company: "empresa X", "trabajo en X", "de la empresa X", "compañía X"
    company_patterns = [
        r'(?:empresa|compañía|trabajo en|de la empresa|de)\s+[:\s]*"?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s&.-]{2,40})"?',
        r'(?:laboro en|estoy en)\s+[:\s]*"?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s&.-]{2,40})"?',
    ]
    for pat in company_patterns:
        comp_match = re.search(pat, text, re.IGNORECASE)
        if comp_match:
            lead["empresa"] = comp_match.group(1).strip().rstrip('.').rstrip(',')
            break

    # Role: "cargo X", "soy el/la X", "gerente de X", "mi cargo es X"
    role_patterns = [
        r'(?:cargo|puesto|rol)[:\s]*:?\s*([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{3,40})',
        r'(?:soy el|soy la|soy)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{3,40})',
        r'(?:gerente|director|coordinador|jefe|analista|presidente|ceo|cto|cfo|founder|fundador)[a-záéíóúñ]*\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s]{2,40})?',
    ]
    for pat in role_patterns:
        role_match = re.search(pat, text, re.IGNORECASE)
        if role_match:
            lead["cargo"] = role_match.group(0).strip().rstrip('.').rstrip(',')
            break

    # Only return if at least 2 fields were found (avoid false positives)
    if len(lead) >= 2:
        return lead
    return {}


async def save_lead(session_id: str, text: str) -> dict | None:
    """Extract and save lead data from a user message. Returns the lead if saved."""
    data = extract_lead_data(text)
    if not data:
        return None

    db = await _get_db()
    try:
        # Check if we already saved a lead for this session
        cursor = await db.execute("SELECT id FROM leads WHERE session_id = ?", (session_id,))
        existing = await cursor.fetchone()
        if existing:
            # Update existing lead
            fields = []
            values = []
            for key, val in data.items():
                if val:
                    fields.append(f"{key} = ?")
                    values.append(val)
            if fields:
                values.append(session_id)
                await db.execute(f"UPDATE leads SET {', '.join(fields)} WHERE session_id = ?", values)
                await db.commit()
        else:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO leads (session_id, nombre, empresa, cargo, whatsapp, correo, mensaje_original, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, data.get("nombre"), data.get("empresa"), data.get("cargo"),
                 data.get("whatsapp"), data.get("correo"), text[:500], now)
            )
            await db.commit()
    finally:
        await db.close()

    return data


async def notify_amelia(lead: dict, session_id: str, user_message: str):
    """Notify Amelia about a new lead via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
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
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM leads ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_lead_count():
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as count FROM leads")
        row = await cursor.fetchone()
        return row["count"]
    finally:
        await db.close()
