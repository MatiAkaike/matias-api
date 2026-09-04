"""Persistencia y automatización de leads del agente web M.A.T.I.A.S."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import smtplib
import ssl
import threading
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

import database

logger = logging.getLogger("matias.leads")
DATABASE_URL = database._build_dsn()
MEETING_URL = os.getenv(
    "GOOGLE_CALENDAR_BOOKING_URL",
    "https://calendar.app.google/YhY1KSgjktrRrcBb6",
)
TELEGRAM_BOT_TOKEN = os.getenv("AMELIA_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = (
    os.getenv("OSCAR_TELEGRAM_CHAT_ID")
    or os.getenv("AMELIA_TELEGRAM_CHAT_ID")
    or os.getenv("TELEGRAM_CHAT_ID", "")
)
ZOHO_SMTP_HOST = os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.com")
ZOHO_SMTP_PORT = int(os.getenv("ZOHO_SMTP_PORT", "587"))
ZOHO_EMAIL = os.getenv("ZOHO_EMAIL", "amelia@akaike.lat")
ZOHO_APP_PASSWORD = os.getenv("ZOHO_APP_PASSWORD", "")
ZOHO_SENDER_NAME = os.getenv("ZOHO_SENDER_NAME", "Amelia — Akaike CRS")
SMTP_LOCK = threading.Lock()


def _extract_lead_data(text: str) -> dict[str, str]:
    """Extrae datos explícitos sin completar ni inferir valores."""
    lead: dict[str, str] = {}
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        lead["correo"] = email_match.group(0).strip().rstrip(".,")

    phone_match = re.search(
        r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3}[\s.-]?\d{2,4}[\s.-]?\d{2,4}",
        text,
    )
    if phone_match:
        digits = re.sub(r"\D", "", phone_match.group(0))
        if 10 <= len(digits) <= 15:
            lead["whatsapp"] = digits

    name_match = re.search(
        r"(?:me llamo|mi nombre es|nombre\s*:)\s*([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ'-]+){1,3})",
        text,
        re.IGNORECASE,
    )
    if name_match:
        lead["nombre"] = name_match.group(1).strip()

    company_match = re.search(
        r"(?:empresa|compañía|trabajo en|de la empresa|de la compañía)\s*:?\s*([A-Za-zÁÉÍÓÚÑáéíóúñ0-9&' -]{2,60})",
        text,
        re.IGNORECASE,
    )
    if company_match:
        lead["empresa"] = company_match.group(1).strip().rstrip(".,")

    role_match = re.search(
        r"(?:cargo|puesto|rol)\s*:?\s*([A-Za-zÁÉÍÓÚÑáéíóúñ -]{2,50})",
        text,
        re.IGNORECASE,
    )
    if role_match:
        lead["cargo"] = role_match.group(1).strip().rstrip(".,")
    return lead


def _public_lead(row: Any) -> dict[str, Any]:
    data = dict(row)
    created = data.get("created_at")
    updated = data.get("updated_at")
    return {
        "id": data.get("id"),
        "session_id": data.get("session_id"),
        "nombre": data.get("name") or "",
        "empresa": data.get("company") or "",
        "cargo": data.get("job_title") or "",
        "whatsapp": data.get("phone") or "",
        "correo": data.get("email") or "",
        "mensaje_original": data.get("original_message") or "",
        "source": data.get("source") or "Web - M.A.T.I.A.S.",
        "ip": data.get("ip") or "",
        "timestamp": created.isoformat() if created is not None and hasattr(created, "isoformat") else created,
        "fecha_actualizacion": updated.isoformat() if updated is not None and hasattr(updated, "isoformat") else updated,
        "email_sent": data.get("email_sent", 0),
        "whatsapp_sent": data.get("whatsapp_sent", 0),
        "telegram_sent": data.get("telegram_sent", 0),
        "email_error": data.get("email_error") or "",
        "whatsapp_error": data.get("whatsapp_error") or "",
        "telegram_error": data.get("telegram_error") or "",
    }


async def init_leads_db() -> None:
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no está configurado; la captura de leads no puede iniciar")
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                session_id TEXT,
                name TEXT,
                email TEXT,
                phone TEXT,
                source TEXT DEFAULT 'Web - M.A.T.I.A.S.',
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        migrations = [
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS company TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS job_title TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS original_message TEXT",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS conversation_json JSONB DEFAULT '[]'::jsonb",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ip TEXT DEFAULT ''",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS country TEXT DEFAULT ''",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS email_sent INTEGER DEFAULT 0",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS email_error TEXT DEFAULT ''",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_sent INTEGER DEFAULT 0",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_error TEXT DEFAULT ''",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS telegram_sent INTEGER DEFAULT 0",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS telegram_error TEXT DEFAULT ''",
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS automation_attempts INTEGER DEFAULT 0",
        ]
        for statement in migrations:
            await conn.execute(statement)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
        try:
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_session_id ON leads(session_id) WHERE session_id IS NOT NULL"
            )
        except Exception as exc:
            logger.warning("No se pudo crear índice único de leads por sesión: %s", exc)


async def _conversation(session_id: str) -> list[dict[str, str]]:
    rows = await database.get_session_interactions(session_id, 50)
    rows = sorted(rows, key=lambda row: str(row.get("timestamp", "")))
    return [{"role": row.get("role", ""), "content": row.get("content", "")} for row in rows]


async def save_lead(session_id: str, text: str, ip: str = "") -> dict[str, Any] | None:
    """Acumula datos compartidos en varios turnos y hace upsert por sesión."""
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no disponible para guardar lead")

    conversation = await _conversation(session_id)
    full_text = "\n".join(item["content"] for item in conversation if item["role"] == "user")
    data = _extract_lead_data(full_text or text)
    if not data:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM leads WHERE session_id=$1", session_id)
        before_email = (row or {}).get("email") if row else ""
        before_phone = (row or {}).get("phone") if row else ""
        payload = json.dumps(conversation, ensure_ascii=False)
        if row:
            row = await conn.fetchrow(
                """
                UPDATE leads SET
                    name=COALESCE($2, name), company=COALESCE($3, company),
                    job_title=COALESCE($4, job_title), phone=COALESCE($5, phone),
                    email=COALESCE($6, email), original_message=COALESCE(original_message, $7),
                    conversation_json=$8::jsonb, ip=COALESCE(NULLIF($9,''), ip), updated_at=NOW()
                WHERE session_id=$1 RETURNING *
                """,
                session_id,
                data.get("nombre"),
                data.get("empresa"),
                data.get("cargo"),
                data.get("whatsapp"),
                data.get("correo"),
                text[:1000],
                payload,
                ip,
            )
        else:
            row = await conn.fetchrow(
                """
                INSERT INTO leads (
                    session_id, name, company, job_title, phone, email,
                    original_message, conversation_json, source, ip, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,'Web - M.A.T.I.A.S.', $9,NOW(),NOW())
                RETURNING *
                """,
                session_id,
                data.get("nombre"),
                data.get("empresa"),
                data.get("cargo"),
                data.get("whatsapp"),
                data.get("correo"),
                text[:1000],
                payload,
                ip,
            )
        lead = _public_lead(row)
        lead["_contact_ready"] = bool(lead.get("correo") or lead.get("whatsapp"))
        lead["_new_contact_channel"] = bool(
            (lead.get("correo") and not before_email) or (lead.get("whatsapp") and not before_phone)
        )
        return lead


async def _update_status(session_id: str, channel: str, sent: bool, error: str = "") -> None:
    if channel not in {"email", "whatsapp", "telegram"}:
        raise ValueError("Canal de automatización inválido")
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no disponible para actualizar automatización")
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE leads SET {channel}_sent=$2, {channel}_error=$3, updated_at=NOW() WHERE session_id=$1",
            session_id,
            1 if sent else 2,
            error[:500],
        )


async def notify_amelia(lead: dict[str, Any], session_id: str, user_message: str = "") -> dict[str, Any]:
    if lead.get("telegram_sent") == 1:
        return {"sent": True, "already_sent": True}
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"sent": False, "error": "Telegram no configurado"}
    fields = {
        "nombre": lead.get("nombre") or "Sin nombre",
        "empresa": lead.get("empresa") or "Sin empresa",
        "cargo": lead.get("cargo") or "Sin cargo",
        "whatsapp": lead.get("whatsapp") or "No proporcionado",
        "correo": lead.get("correo") or "No proporcionado",
    }
    message = (
        "🆕 <b>Nuevo registro en M.A.T.I.A.S. Web</b>\n\n"
        f"👤 <b>Nombre:</b> {html.escape(str(fields['nombre']))}\n"
        f"🏢 <b>Empresa:</b> {html.escape(str(fields['empresa']))}\n"
        f"💼 <b>Cargo:</b> {html.escape(str(fields['cargo']))}\n"
        f"📱 <b>WhatsApp:</b> {html.escape(str(fields['whatsapp']))}\n"
        f"📧 <b>Correo:</b> {html.escape(str(fields['correo']))}\n\n"
        "Amelia enviará la información y coordinará la reunión."
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            )
            response.raise_for_status()
        await _update_status(session_id, "telegram", True)
        return {"sent": True}
    except Exception as exc:
        safe_error = str(exc).replace(TELEGRAM_BOT_TOKEN, "***")
        await _update_status(session_id, "telegram", False, safe_error)
        return {"sent": False, "error": safe_error}


def _build_lead_email(nombre: str = "") -> str:
    saludo = f"Hola {html.escape(nombre)}" if nombre else "Hola"
    return f"""<html><body style="font-family:Arial,sans-serif;color:#1a2440;max-width:600px;margin:auto">
<h2 style="color:#0ea5e9">{saludo},</h2>
<p>Gracias por conversar con M.A.T.I.A.S. y por tu interés en Akaike Credit Risk Solutions.</p>
<p>Ayudamos a entidades que otorgan crédito a construir modelos de scoring personalizados, automatizar decisiones e integrar analítica de riesgo mediante APIs.</p>
<p><a href="{MEETING_URL}" style="background:#0ea5e9;color:white;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold">Coordinar una reunión con Oscar</a></p>
<p>El enlace consulta la disponibilidad real del calendario y confirma automáticamente la invitación.</p>
<p style="color:#64748b;font-size:13px">Puedes responder este correo; Amelia continuará acompañándote.</p>
<p style="color:#94a3b8;font-size:12px">Amelia · Akaike Credit Risk Solutions · <a href="https://akaike.lat">akaike.lat</a></p>
</body></html>"""


def _smtp_send(to_email: str, message: MIMEMultipart) -> None:
    with SMTP_LOCK:
        context = ssl.create_default_context()
        with smtplib.SMTP(ZOHO_SMTP_HOST, ZOHO_SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(ZOHO_EMAIL, ZOHO_APP_PASSWORD)
            server.sendmail(ZOHO_EMAIL, to_email, message.as_string())


async def send_lead_email(lead: dict[str, Any], session_id: str) -> dict[str, Any]:
    if lead.get("email_sent") == 1:
        return {"sent": True, "already_sent": True}
    email = (lead.get("correo") or "").strip()
    if not email:
        return {"sent": False, "error": "Lead sin correo"}
    if not ZOHO_APP_PASSWORD:
        return {"sent": False, "error": "Zoho SMTP no configurado"}
    message = MIMEMultipart("alternative")
    message["Subject"] = "Información de M.A.T.I.A.S. y reunión con Akaike"
    message["From"] = f"{ZOHO_SENDER_NAME} <{ZOHO_EMAIL}>"
    message["To"] = email
    message.attach(MIMEText(_build_lead_email(lead.get("nombre") or ""), "html", "utf-8"))
    last_error = ""
    for attempt in range(3):
        try:
            await asyncio.to_thread(_smtp_send, email, message)
            await _update_status(session_id, "email", True)
            return {"sent": True, "attempts": attempt + 1}
        except Exception as exc:
            last_error = str(exc).replace(ZOHO_APP_PASSWORD, "***")
            if attempt < 2:
                await asyncio.sleep(2**attempt)
    await _update_status(session_id, "email", False, last_error)
    return {"sent": False, "error": last_error, "attempts": 3}


async def process_lead_automation(lead: dict[str, Any], session_id: str, user_message: str = "") -> None:
    """Ejecuta canales disponibles; el worker local reintenta lo pendiente."""
    if not lead.get("correo") and not lead.get("whatsapp"):
        return
    try:
        await notify_amelia(lead, session_id, user_message)
        if lead.get("correo"):
            await send_lead_email(lead, session_id)
    except Exception:
        logger.exception("Fallo en automatización de lead %s", session_id)


async def mark_whatsapp_status(session_id: str, sent: bool, error: str = "") -> None:
    await _update_status(session_id, "whatsapp", sent, error)


async def mark_email_status(session_id: str, sent: bool, error: str = "") -> None:
    await _update_status(session_id, "email", sent, error)


async def get_pending_leads(limit: int = 20, claim: bool = True) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM leads
            WHERE automation_attempts < 5 AND (
                (email IS NOT NULL AND email <> '' AND email_sent <> 1) OR
                (phone IS NOT NULL AND phone <> '' AND whatsapp_sent <> 1) OR
                ((email IS NOT NULL AND email <> '') OR (phone IS NOT NULL AND phone <> ''))
                    AND telegram_sent <> 1
            )
            ORDER BY created_at ASC LIMIT $1
            """,
            limit,
        )
        if rows and claim:
            ids = [row["id"] for row in rows]
            await conn.execute(
                "UPDATE leads SET automation_attempts=automation_attempts+1, updated_at=NOW() WHERE id=ANY($1::int[])",
                ids,
            )
        return [_public_lead(row) for row in rows]


async def get_all_leads(limit: int = 50) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM leads ORDER BY created_at DESC LIMIT $1", limit)
        return [_public_lead(row) for row in rows]


async def get_lead_count() -> int:
    pool = await database._get_pg_pool()
    if not pool:
        return 0
    async with pool.acquire() as conn:
        return int(await conn.fetchval("SELECT COUNT(*) FROM leads"))


async def get_lead_by_session(session_id: str) -> dict[str, Any] | None:
    pool = await database._get_pg_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM leads WHERE session_id=$1", session_id)
        return _public_lead(row) if row else None


async def get_leads_by_ip(ip: str) -> list[dict[str, Any]]:
    if not ip:
        return []
    pool = await database._get_pg_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM leads WHERE ip=$1 ORDER BY created_at DESC", ip)
        return [_public_lead(row) for row in rows]


async def get_automation_status() -> dict[str, Any]:
    pool = await database._get_pg_pool()
    if not pool:
        return {"database": "unavailable"}
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) total,
                   COUNT(*) FILTER (WHERE email IS NOT NULL AND email<>'' AND email_sent<>1) pending_email,
                   COUNT(*) FILTER (WHERE phone IS NOT NULL AND phone<>'' AND whatsapp_sent<>1) pending_whatsapp,
                   COUNT(*) FILTER (WHERE telegram_sent<>1) pending_telegram,
                   COUNT(*) FILTER (WHERE email_sent=2 OR whatsapp_sent=2 OR telegram_sent=2) failures
            FROM leads
            """
        )
        return dict(row)
