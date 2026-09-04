#!/Users/ogutimo/.openclaw-venv/bin/python
"""Procesa leads web pendientes y activa a Amelia por canales locales."""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

OPENCLAW = Path("/Volumes/OpenClaw/OPENCLAW")
MATIAS_API = Path(os.getenv("MATIAS_API_PATH", "/Volumes/OpenClaw/Matias Seek/api"))
load_dotenv(OPENCLAW / ".env")
load_dotenv(Path("/Volumes/OpenClaw/Matias Seek/config/.env"), override=False)
sys.path.insert(0, str(OPENCLAW))
sys.path.insert(0, str(MATIAS_API))

import lead_service
from core.shared_tools.send_whatsapp import send_whatsapp_message
from core.shared_tools.zoho_mail_amelia import enviar_html

BOOKING_URL = os.getenv(
    "GOOGLE_CALENDAR_BOOKING_URL",
    "https://calendar.app.google/YhY1KSgjktrRrcBb6",
)
LOG_PATH = Path.home() / ".openclaw-runtime" / "matias-lead-worker" / "worker.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("matias-lead-worker")


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 10 and digits.startswith("3"):
        return "57" + digits
    return digits


def _whatsapp_message(lead: dict) -> str:
    nombre = (lead.get("nombre") or "").strip()
    saludo = f"Hola {nombre}, ¿cómo estás? 😊" if nombre else "Hola, ¿cómo estás? 😊"
    return (
        f"{saludo} Soy Amelia, de Akaike. Gracias por conversar con M.A.T.I.A.S.; "
        "ayudamos a entidades que otorgan crédito con modelos de scoring personalizados y automatización de decisiones.\n\n"
        f"Puedes elegir aquí el horario que mejor te sirva para conversar con Oscar:\n{BOOKING_URL}"
    )


def _email_body(lead: dict) -> str:
    nombre = html.escape((lead.get("nombre") or "").strip())
    saludo = f"Hola {nombre}," if nombre else "Hola,"
    return (
        f"<p>{saludo}</p>"
        "<p>Gracias por conversar con M.A.T.I.A.S. Ayudamos a entidades que otorgan crédito "
        "con modelos de scoring personalizados, analítica y automatización de decisiones.</p>"
        f'<p><a href="{BOOKING_URL}">Elige aquí un horario disponible para conversar con Oscar</a>.</p>'
        "<p>Puedes responder este correo; continuaré acompañándote.</p>"
    )


async def _process_lead(lead: dict, dry_run: bool = False) -> dict:
    session_id = lead["session_id"]
    result = {"session_id": session_id, "email": "skip", "telegram": "skip", "whatsapp": "skip"}

    if lead.get("telegram_sent") == 3:
        if dry_run:
            result["telegram"] = "dry-run"
        else:
            sent = await lead_service.notify_amelia(lead, session_id)
            result["telegram"] = "sent" if sent.get("sent") else "error"

    if lead.get("correo") and lead.get("email_sent") == 3:
        if dry_run:
            result["email"] = "dry-run"
        else:
            try:
                sent = await asyncio.to_thread(
                    enviar_html,
                    to=lead["correo"],
                    subject="Información de M.A.T.I.A.S. y reunión con Akaike",
                    html_body=_email_body(lead),
                )
                ok = sent.get("status") == "OK"
                await lead_service.mark_email_status(session_id, ok, sent.get("error", ""))
                result["email"] = "sent" if ok else "error"
            except Exception as exc:
                await lead_service.mark_email_status(session_id, False, str(exc))
                result["email"] = "error"

    phone = _normalize_phone(lead.get("whatsapp") or "")
    if phone and lead.get("whatsapp_sent") == 3:
        if dry_run:
            result["whatsapp"] = "dry-run"
        else:
            try:
                sent = await asyncio.to_thread(
                    send_whatsapp_message,
                    phone,
                    _whatsapp_message(lead),
                    "personal",
                    lead.get("nombre") or "Lead M.A.T.I.A.S. Web",
                )
                ok = sent.get("status") == "OK"
                await lead_service.mark_whatsapp_status(session_id, ok, sent.get("error", ""))
                result["whatsapp"] = "sent" if ok else "error"
            except Exception as exc:
                await lead_service.mark_whatsapp_status(session_id, False, str(exc))
                result["whatsapp"] = "error"
    return result


async def run_once(dry_run: bool = False) -> dict:
    pending = await lead_service.get_pending_leads(20, claim=not dry_run)
    results = []
    for lead in pending:
        results.append(await _process_lead(lead, dry_run=dry_run))
    if pending:
        logger.info("Procesados %s leads; estados=%s", len(pending), results)
    return {"pending": len(pending), "results": results}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    summary = asyncio.run(run_once(dry_run=dry))
    print(f"pending={summary['pending']}")
