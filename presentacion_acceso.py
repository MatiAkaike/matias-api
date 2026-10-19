"""Acceso a la presentación completa (akaike.lat/presentacion).

Quien llega sin enlace personal ve hasta la diapositiva 3. Para seguir deja nombre, correo y
WhatsApp, que se validan aquí (formato, dominio con MX, correos desechables y número por país)
y se guardan como lead con la fuente «Presentación M.A.T.I.A.S.»; el worker de Amelia hace el
seguimiento como con cualquier lead.

Los clientes de Oscar entran con un enlace personal (?p=<token>) que se crea por el endpoint de
administración y no pide datos.
"""

from __future__ import annotations

import os
import re
import secrets
from typing import Any

import dns.asyncresolver
import dns.exception
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType

import database

FUENTE = "Presentación M.A.T.I.A.S."
# Un enlace personal se abre desde máximo estas IP distintas; desde una nueva se piden los datos.
MAX_IPS = int(os.getenv("PRESENTACION_ENLACE_MAX_IPS", "3"))

# Proveedores de correo temporal o desechable más usados (se bloquean; Gmail, Hotmail, etc. sí se aceptan).
DESECHABLES = frozenset({
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com", "10minutemail.com",
    "10minutemail.net", "tempmail.com", "temp-mail.org", "temp-mail.io", "yopmail.com", "yopmail.net",
    "trashmail.com", "getnada.com", "nada.email", "dispostable.com", "maildrop.cc", "mailnesia.com",
    "throwawaymail.com", "fakeinbox.com", "mintemail.com", "mohmal.com", "emailondeck.com",
    "tempail.com", "tempr.email", "discard.email", "spamgourmet.com", "mytemp.email", "burnermail.io",
    "moakt.com", "inboxkitten.com", "1secmail.com", "1secmail.net", "1secmail.org", "linshiyouxiang.net",
    "mailpoof.com", "emailfake.com", "fakemail.net", "trashmail.de", "wegwerfmail.de", "spam4.me",
})

_CORREO = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+)$")
_NOMBRE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'´`.\- ]{2,80}$")


def validar_nombre(nombre: str) -> tuple[str, str | None]:
    limpio = " ".join((nombre or "").split())
    if len(limpio) < 3 or not _NOMBRE.match(limpio) or not re.search(r"[A-Za-zÀ-ÿ]{2,}", limpio):
        return limpio, "Escriba su nombre completo."
    return limpio, None


async def _dominio_recibe_correo(dominio: str) -> bool:
    """True si el dominio tiene MX (o, en su defecto, una dirección A/AAAA, como permite el RFC 5321)."""
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 4.0
    for tipo in ("MX", "A", "AAAA"):
        try:
            respuesta = await resolver.resolve(dominio, tipo)
            if tipo == "MX" and any(str(r.exchange).strip(".") in ("", ".") for r in respuesta):
                return False  # MX nulo (RFC 7505): el dominio declara que no recibe correo
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            return False
        except (dns.resolver.NoAnswer, dns.exception.Timeout):
            continue
    return False


async def validar_correo(correo: str) -> tuple[str, str | None]:
    limpio = (correo or "").strip().lower()
    m = _CORREO.match(limpio)
    if not m or ".." in limpio or len(limpio) > 254:
        return limpio, "Escriba un correo válido."
    dominio = m.group(1)
    if dominio in DESECHABLES or any(dominio.endswith("." + d) for d in DESECHABLES):
        return limpio, "Use un correo permanente, no uno temporal."
    if not await _dominio_recibe_correo(dominio):
        return limpio, "Ese dominio no recibe correos. Revise que esté bien escrito."
    return limpio, None


def validar_whatsapp(numero: str, pais: str) -> tuple[str, str | None]:
    """Valida el número para el país y devuelve los dígitos internacionales (sin «+»)."""
    try:
        n = phonenumbers.parse(numero or "", (pais or "CO").upper())
    except NumberParseException:
        return "", "Escriba un número de WhatsApp válido."
    if not phonenumbers.is_valid_number(n):
        return "", "Ese número no es válido para el país elegido."
    if phonenumbers.number_type(n) not in (PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE):
        return "", "Escriba un número de celular con WhatsApp."
    return phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.E164).lstrip("+"), None


async def init_db() -> None:
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no está configurado; el acceso a la presentación no puede iniciar")
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS presentacion_enlaces (
                token TEXT PRIMARY KEY,
                cliente TEXT NOT NULL,
                creado TIMESTAMPTZ DEFAULT NOW(),
                usos INTEGER DEFAULT 0,
                ultimo_uso TIMESTAMPTZ,
                activo BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("ALTER TABLE presentacion_enlaces ENABLE ROW LEVEL SECURITY")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS presentacion_enlace_ips (
                token TEXT NOT NULL REFERENCES presentacion_enlaces(token) ON DELETE CASCADE,
                ip TEXT NOT NULL,
                primera TIMESTAMPTZ DEFAULT NOW(),
                ultima TIMESTAMPTZ DEFAULT NOW(),
                usos INTEGER DEFAULT 1,
                PRIMARY KEY (token, ip)
            )
        """)
        await conn.execute("ALTER TABLE presentacion_enlace_ips ENABLE ROW LEVEL SECURITY")


async def crear_enlace(cliente: str) -> str:
    token = secrets.token_urlsafe(12)
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO presentacion_enlaces (token, cliente) VALUES ($1, $2)", token, cliente.strip()[:120])
    return token


async def listar_enlaces(limit: int = 100) -> list[dict[str, Any]]:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT e.token, e.cliente, e.creado, e.usos, e.ultimo_uso, e.activo,
                      (SELECT COUNT(*) FROM presentacion_enlace_ips i WHERE i.token = e.token) AS ips
               FROM presentacion_enlaces e ORDER BY e.creado DESC LIMIT $1""", limit)
    return [{**dict(r), "creado": str(r["creado"]), "ultimo_uso": str(r["ultimo_uso"] or ""), "max_ips": MAX_IPS} for r in rows]


async def desactivar_enlace(token: str) -> bool:
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        r = await conn.execute("UPDATE presentacion_enlaces SET activo = FALSE WHERE token=$1", token)
    return r.endswith(" 1")


async def usar_enlace(token: str, ip: str = "") -> tuple[str | None, str]:
    """Devuelve (cliente, motivo). Válido si el enlace está activo y la IP es una de las primeras MAX_IPS."""
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", token):
        return None, "invalido"
    ip = (ip or "desconocida")[:64]
    pool = await database._get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            enlace = await conn.fetchrow(
                "SELECT cliente FROM presentacion_enlaces WHERE token=$1 AND activo FOR UPDATE", token)
            if not enlace:
                return None, "invalido"
            conocida = await conn.fetchval(
                "UPDATE presentacion_enlace_ips SET ultima = NOW(), usos = usos + 1 WHERE token=$1 AND ip=$2 RETURNING 1", token, ip)
            if not conocida:
                usadas = await conn.fetchval("SELECT COUNT(*) FROM presentacion_enlace_ips WHERE token=$1", token)
                if usadas >= MAX_IPS:
                    return None, "limite"
                await conn.execute("INSERT INTO presentacion_enlace_ips (token, ip) VALUES ($1, $2)", token, ip)
            await conn.execute("UPDATE presentacion_enlaces SET usos = usos + 1, ultimo_uso = NOW() WHERE token=$1", token)
    return enlace["cliente"], "ok"


async def guardar_lead(session_id: str, nombre: str, correo: str, whatsapp: str, pais: str, ip: str, contexto: str) -> None:
    """Upsert por sesión en «leads»: el worker de Amelia hace el seguimiento (correo, WhatsApp, aviso)."""
    pool = await database._get_pg_pool()
    if not pool:
        raise RuntimeError("PostgreSQL no disponible para guardar el lead")
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO leads (session_id, name, email, phone, original_message, source, ip, country, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW(),NOW())
            ON CONFLICT (session_id) WHERE session_id IS NOT NULL DO UPDATE SET
                name=EXCLUDED.name,
                email=EXCLUDED.email,
                phone=EXCLUDED.phone,
                original_message=COALESCE(leads.original_message, EXCLUDED.original_message),
                source=EXCLUDED.source,
                ip=COALESCE(NULLIF(EXCLUDED.ip,''), leads.ip),
                country=EXCLUDED.country,
                email_sent=CASE WHEN EXCLUDED.email IS DISTINCT FROM leads.email THEN 0 ELSE leads.email_sent END,
                email_attempts=CASE WHEN EXCLUDED.email IS DISTINCT FROM leads.email THEN 0 ELSE leads.email_attempts END,
                whatsapp_sent=CASE WHEN EXCLUDED.phone IS DISTINCT FROM leads.phone THEN 0 ELSE leads.whatsapp_sent END,
                whatsapp_attempts=CASE WHEN EXCLUDED.phone IS DISTINCT FROM leads.phone THEN 0 ELSE leads.whatsapp_attempts END,
                telegram_sent=CASE WHEN EXCLUDED.email IS DISTINCT FROM leads.email OR EXCLUDED.phone IS DISTINCT FROM leads.phone THEN 0 ELSE leads.telegram_sent END,
                telegram_attempts=CASE WHEN EXCLUDED.email IS DISTINCT FROM leads.email OR EXCLUDED.phone IS DISTINCT FROM leads.phone THEN 0 ELSE leads.telegram_attempts END,
                updated_at=NOW()
            """,
            session_id, nombre, correo, whatsapp, contexto[:1000], FUENTE, ip, (pais or "").upper()[:2],
        )
