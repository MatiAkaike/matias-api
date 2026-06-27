import os
import re
import json
import httpx
import asyncio
import psycopg2
import psycopg2.extras
import smtplib
import ssl
import time as _time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from pathlib import Path

def _build_dsn():
    """Construye DSN igual que database.py."""
    host = os.getenv("SUPABASE_HOST", "")
    pw = os.getenv("SUPABASE_PASSWORD", "")
    user = os.getenv("SUPABASE_USER", "postgres")
    port = os.getenv("SUPABASE_PORT", "6543")
    db = os.getenv("SUPABASE_DB", "postgres")
    if host and pw:
        from urllib.parse import quote_plus
        return f"postgresql://{user}:{quote_plus(pw)}@{host}:{port}/{db}"
    return os.getenv("DATABASE_URL", "")

DATABASE_URL = _build_dsn()
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
        print("[LEADS] DATABASE_URL vacio — leads deshabilitado")
        return
    try:
        conn = await _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        print("[LEADS] Conexion DB OK")

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
                notified INTEGER DEFAULT 0,
                ip TEXT DEFAULT ''
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_ts ON leads(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_session ON leads(session_id)")
        # Migración: agregar columna ip si no existe
        try:
            cur.execute("ALTER TABLE leads ADD COLUMN ip TEXT DEFAULT ''")
        except Exception:
            pass  # ya existe
        # Migración: columnas nuevas para webhook de leads
        for col, tipo in [("pais", "TEXT"), ("source", "TEXT DEFAULT 'Web - M.A.T.I.A.S. Bot'"),
                          ("conversacion_json", "JSONB"), ("fecha_actualizacion", "TIMESTAMPTZ"),
                          ("email_sent", "INTEGER DEFAULT 0"), ("email_error", "TEXT")]:
            try:
                cur.execute(f"ALTER TABLE leads ADD COLUMN {col} {tipo}")
            except Exception:
                pass
        # Si source es NULL, actualizar a valor por defecto
        try:
            cur.execute("UPDATE leads SET source = 'Web - M.A.T.I.A.S. Bot' WHERE source IS NULL")
        except Exception:
            pass
        print("[LEADS] init_leads_db completo")
        cur.close()
    except Exception as e:
        print(f"[LEADS] Error en init_leads_db: {e}")


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

    # Company: "empresa X", "trabajo en X", "de X", "en X"
    comp_match = re.search(
        r'(?:empresa|compañía|trabajo en|de la empresa|de la compañía)\s+[:\s]*"?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s&.-]{2,40})"?',
        text, re.IGNORECASE
    )
    if not comp_match:
        comp_match = re.search(
            r'(?:de|en)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]{2,30}(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9]+){0,2})',
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

    if "correo" in lead or len(lead) >= 2:
        return lead
    return {}


async def save_lead(session_id: str, text: str, ip: str = "") -> dict | None:
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
            if ip:
                sets.append("ip = %s")
                vals.append(ip)
            if sets:
                vals.append(session_id)
                cur.execute(f"UPDATE leads SET {', '.join(sets)} WHERE session_id = %s", vals)
        else:
            now = datetime.now(timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO leads (session_id, nombre, empresa, cargo, whatsapp, correo, mensaje_original, timestamp, ip) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (session_id, data.get("nombre"), data.get("empresa"), data.get("cargo"),
                 data.get("whatsapp"), data.get("correo"), text[:500], now, ip)
            )
        cur.close()
    except Exception:
        return None

    return data


async def notify_amelia(lead: dict, session_id: str, user_message: str):
    """Notifica a Amelia sobre un nuevo lead via Telegram."""
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


# ─── Email sending via Zoho SMTP ────────────────────────────────────────────

# Config Zoho SMTP
ZOHO_SMTP_HOST = os.getenv("ZOHO_SMTP_HOST", "smtp.zoho.com")
ZOHO_SMTP_PORT = int(os.getenv("ZOHO_SMTP_PORT", "587"))
ZOHO_EMAIL = os.getenv("ZOHO_EMAIL", "amelia@akaike.lat")
ZOHO_APP_PASSWORD = os.getenv("ZOHO_APP_PASSWORD", "")
ZOHO_SENDER_NAME = os.getenv("ZOHO_SENDER_NAME", "Amelia — Akaike CRS")

# URL demo y PDF
DEMO_URL = "https://calendar.app.google/sb4W9ja1WLUAaaMs9"
PDF_PATH = os.getenv("LEAD_PDF_PATH", os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Akaike CRS/MATIAS/"
    "Akaike Presentación de Servicios 2026 - M.A.T.I.A.S.SP.pdf"))
PDF_GDRIVE_LINK = os.getenv("LEAD_PDF_GDRIVE_LINK",
    "https://drive.google.com/file/d/1Qq6QVKl2h0FqNbLf-TWjKOfPGP6-MiYP/view?usp=drive_link")

PDF_MAX_SIZE = 7_500_000  # 7.5 MB


def _build_lead_email(nombre: str, empresa: str, correo: str) -> str:
    """Construye el HTML del correo de lead."""
    saludo = f"Hola {nombre}" if nombre else "Hola"
    return f"""\
<html><body style="font-family:Arial,sans-serif;color:#1a2440;max-width:600px;margin:0 auto">
<h2 style="color:#0ea5e9">{saludo},</h2>
<p>Gracias por tu interés en <strong>M.A.T.I.A.S.</strong>, la inteligencia artificial de credit scoring de Akaike Credit Risk Solutions.</p>
<p>M.A.T.I.A.S. ayuda a fintechs, cooperativas y entidades de crédito a:</p>
<ul>
  <li>Mejorar hasta un <strong>44% la tasa de aprobación</strong></li>
  <li>Reducir hasta un <strong>36% el NPL/ICV</strong></li>
  <li>Automatizar decisiones de originación, seguimiento y cobranza</li>
  <li>Procesar solicitudes 7x24 con conexión a burós y lectura de documentos</li>
</ul>
<p style="margin:24px 0">
  <a href="{DEMO_URL}" style="background:#0ea5e9;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:16px">
    Agendar demo — 30 minutos
  </a>
</p>
<p style="color:#64748b;font-size:13px">Adjunto encontrarás la presentación de servicios de Akaike.<br>
Si tenés preguntas, respondé este correo o escribime a amelia@akaike.lat.</p>
<p style="color:#94a3b8;font-size:12px;margin-top:24px">
Amelia · Segunda al Mando<br>
Akaike Credit Risk Solutions · <a href="https://akaike.lat">akaike.lat</a>
</p>
</body></html>"""


async def send_lead_email(lead: dict, session_id: str) -> dict:
    """Envía correo de seguimiento al lead con reintentos.
    Retorna dict con status y error si falla."""
    if not ZOHO_APP_PASSWORD:
        return {"sent": False, "error": "ZOHO_APP_PASSWORD no configurado"}

    correo = lead.get("correo", "")
    if not correo:
        return {"sent": False, "error": "Sin correo en lead"}

    nombre = lead.get("nombre", "")
    html = _build_lead_email(nombre, lead.get("empresa", ""), correo)
    subject = "M.A.T.I.A.S. — Información de Akaike Credit Risk Solutions"

    # Construir mensaje multipart
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{ZOHO_SENDER_NAME} <{ZOHO_EMAIL}>"
    msg["To"] = correo
    msg.attach(MIMEText(html, "html"))

    # Adjuntar PDF o link de Drive
    pdf_attached = False
    pdf_path = Path(PDF_PATH)
    if pdf_path.exists() and pdf_path.stat().st_size < PDF_MAX_SIZE:
        try:
            with open(pdf_path, "rb") as f:
                part = MIMEBase("application", "pdf")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition",
                    f'attachment; filename="{pdf_path.name}"')
                msg.attach(part)
                pdf_attached = True
        except Exception:
            pass

    if not pdf_attached:
        # Agregar link de Google Drive como alternativa
        link_note = MIMEText(
            f'<p style="font-size:12px;color:#94a3b8;margin-top:16px">'
            f'📎 <a href="{PDF_GDRIVE_LINK}">Descargar presentación de servicios (PDF)</a></p>',
            "html")
        msg.attach(link_note)

    # Retry con backoff exponencial
    last_error = ""
    for attempt in range(3):
        try:
            context = ssl.create_default_context()
            server = await asyncio.to_thread(smtplib.SMTP, ZOHO_SMTP_HOST, ZOHO_SMTP_PORT, timeout=15)
            server.starttls(context=context)
            server.login(ZOHO_EMAIL, ZOHO_APP_PASSWORD)
            await asyncio.to_thread(server.sendmail, ZOHO_EMAIL, correo, msg.as_string())
            server.quit()

            # Marcar como enviado
            await _mark_email_sent(session_id, True)
            return {"sent": True, "to": correo, "attempts": attempt + 1}

        except Exception as e:
            last_error = str(e).replace(ZOHO_APP_PASSWORD, "***")
            if attempt < 2:
                delay = 2 ** attempt
                await asyncio.sleep(delay)

    # Fallaron los 3 intentos
    await _mark_email_sent(session_id, False, last_error)
    # Notificar fallo a Telegram
    await _notify_email_failure(lead, session_id, last_error)
    return {"sent": False, "error": last_error, "attempts": 3}


async def _mark_email_sent(session_id: str, success: bool, error: str = ""):
    """Actualiza el estado de envío de email en la BD."""
    if not DATABASE_URL:
        return
    try:
        conn = await _get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE leads SET email_sent = %s, email_error = %s, "
            "fecha_actualizacion = NOW() WHERE session_id = %s",
            (1 if success else 2, error[:500] if error else "", session_id))
        cur.close()
    except Exception:
        pass


async def _notify_email_failure(lead: dict, session_id: str, error: str):
    """Notifica fallo de envío de email a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    correo = lead.get("correo", "?")
    msg = (f"⚠️ *Fallo envío de correo a lead*\n"
           f"📧 {correo}\n"
           f"Error: {error[:300]}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
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


async def get_lead_by_session(session_id: str) -> dict | None:
    """Obtener lead por session_id."""
    if not DATABASE_URL:
        return None
    try:
        conn = await _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM leads WHERE session_id = %s", (session_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    except Exception:
        return None


async def get_leads_by_ip(ip: str) -> list[dict]:
    """Obtener todos los leads de una IP."""
    if not DATABASE_URL or not ip:
        return []
    try:
        conn = await _get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM leads WHERE ip = %s ORDER BY timestamp DESC", (ip,))
        rows = cur.fetchall()
        cur.close()
        return [dict(row) for row in rows]
    except Exception:
        return []
