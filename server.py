import json
import hmac
import os
import re
import uuid
import time
import threading
import asyncio
import ipaddress
from collections import deque
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load .env for local development
load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

# ─── System prompt ───────────────────────────────────────────────────────────

import analytics_store
import database
import lead_service as leads

try:
    from agent_prompt import SYSTEM_PROMPT
except ImportError:
    # Fallback: load from config.json (local dev)
    CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"
    with open(CONFIG_PATH) as f:
        raw = f.read()
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        escaped = re.sub(
            r'"(?:[^"\\]|\\.)*"',
            lambda m: m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'),
            raw,
        )
        config = json.loads(escaped)
    SYSTEM_PROMPT = config["agents"]["list"][0]["systemPrompt"]

# ─── Model config (env vars with sensible defaults) ──────────────────────────

MODEL_ID = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
MEETING_URL = os.getenv(
    "GOOGLE_CALENDAR_BOOKING_URL",
    "https://calendar.app.google/up2iyv5hJkJpRJta9",
)
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))
ADMIN_TOKEN = os.getenv("MATIAS_ADMIN_TOKEN", "")

# ─── Alerta de abuso por IP ───────────────────────────────────────────────────

ABUSE_THRESHOLD = int(os.getenv("ABUSE_SESSION_THRESHOLD", "20"))  # sesiones por IP
ABUSE_COOLDOWN = int(os.getenv("ABUSE_ALERT_COOLDOWN", "3600"))    # segundos entre alertas por IP
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OSCAR_CHAT_ID = os.getenv("OSCAR_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")

# {ip: {"sessions": set(), "last_alert": timestamp}}
ip_tracker: dict[str, dict] = {}
ip_tracker_lock = threading.Lock()
rate_tracker: dict[tuple[str, str], deque[float]] = {}
rate_tracker_lock = threading.Lock()

CHAT_QUOTA_LIMIT = 10
CHAT_QUOTA_WINDOW = 24 * 3600  # segundos antes de resetear la cuota por IP
_chat_quota: dict[str, tuple[int, float]] = {}
_chat_quota_lock = threading.Lock()


def _consume_chat_quota(ip: str) -> bool:
    """Devuelve True si aún queda cuota de chat para la IP; consume un turno."""
    if not ip or ip == "unknown":
        return True
    now = time.time()
    with _chat_quota_lock:
        count, last_seen = _chat_quota.get(ip, (0, now))
        if now - last_seen > CHAT_QUOTA_WINDOW:
            count = 0
        if count >= CHAT_QUOTA_LIMIT:
            return False
        _chat_quota[ip] = (count + 1, now)
        return True


def _get_client_ip(request: Request) -> str:
    """Usa la IP normalizada por Uvicorn; solo recurre a XFF desde proxy privado."""
    peer = request.client.host if request.client else ""
    try:
        if peer and not ipaddress.ip_address(peer).is_private:
            return peer
    except ValueError:
        pass
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        for candidate in reversed([value.strip() for value in forwarded.split(",")]):
            try:
                if not ipaddress.ip_address(candidate).is_private:
                    return candidate
            except ValueError:
                continue
    return peer or "unknown"


def _allow_request(ip: str, bucket: str, limit: int, window: int = 60) -> bool:
    now = time.time()
    key = (ip, bucket)
    with rate_tracker_lock:
        timestamps = rate_tracker.setdefault(key, deque())
        while timestamps and timestamps[0] <= now - window:
            timestamps.popleft()
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True


async def _send_abuse_alert(ip: str, session_count: int, last_session_id: str):
    """Envía Telegram a Oscar via el bot de Amelia cuando se detecta abuso."""
    msg = (
        f"🚨 <b>ALERTA DE ABUSO — M.A.T.I.A.S. Web</b>\n\n"
        f"<b>IP:</b> <code>{ip}</code>\n"
        f"<b>Sesiones activas:</b> {session_count}\n"
        f"<b>Última sesión:</b> <code>{last_session_id}</code>\n\n"
        f"⚠️ Una misma IP ha abierto {session_count}+ conversaciones. "
        f"Podría ser un bot, ataque DoS o scraping intensivo.\n\n"
        f"📊 <a href=\"https://matias-api-ka16.onrender.com/api/interactions/stats\">Ver estadísticas</a>"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": OSCAR_CHAT_ID,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if resp.status_code != 200:
                print(f"[ABUSE-ALERT] Error Telegram: {resp.status_code} {resp.text}")
            else:
                print(f"[ABUSE-ALERT] Notificado a Oscar — IP {ip} con {session_count} sesiones")
    except Exception as e:
        print(f"[ABUSE-ALERT] Fallo al enviar Telegram: {e}")


def _check_ip_abuse(ip: str, session_id: str) -> bool:
    """Registra sesión por IP. Si alcanza el umbral, dispara alerta.
    Retorna True si se disparó alerta."""
    if ip == "unknown" or ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168."):
        return False  # ignorar IPs locales

    now = time.time()
    with ip_tracker_lock:
        if ip not in ip_tracker:
            ip_tracker[ip] = {"sessions": set(), "last_alert": 0}

        entry = ip_tracker[ip]
        entry["sessions"].add(session_id)
        count = len(entry["sessions"])

        # ¿Disparar alerta?
        if count >= ABUSE_THRESHOLD and (now - entry["last_alert"]) > ABUSE_COOLDOWN:
            entry["last_alert"] = now
            return True
    return False

# ─── CORS origins — abierto para presentaciones y widgets ─────────────────────

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "https://akaike.lat,https://www.akaike.lat").split(",")
    if origin.strip()
]

# ─── Session store ───────────────────────────────────────────────────────────

SESSION_TTL = 3600
MAX_HISTORY = 20


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.last_access = time.time()
        self.created_at = time.time()

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > MAX_HISTORY + 1:
            self.messages = [self.messages[0]] + self.messages[-(MAX_HISTORY):]
        self.last_access = time.time()


sessions: dict[str, Session] = {}
sessions_lock = threading.Lock()
session_request_locks: dict[str, asyncio.Lock] = {}


def _cleanup_sessions():
    now = time.time()
    with sessions_lock:
        expired = [sid for sid, s in sessions.items() if now - s.last_access > SESSION_TTL]
        for sid in expired:
            del sessions[sid]
            session_request_locks.pop(sid, None)
        stale_new_locks = [
            key for key, lock in session_request_locks.items()
            if key.startswith("new:") and not lock.locked()
        ]
        for key in stale_new_locks:
            session_request_locks.pop(key, None)
    with rate_tracker_lock:
        stale_rate_keys = [
            key for key, timestamps in rate_tracker.items()
            if not timestamps or timestamps[-1] < now - 300
        ]
        for key in stale_rate_keys:
            del rate_tracker[key]
    with _chat_quota_lock:
        stale_quota_ips = [
            ip for ip, (count, last_seen) in _chat_quota.items()
            if now - last_seen > CHAT_QUOTA_WINDOW * 2
        ]
        for ip in stale_quota_ips:
            del _chat_quota[ip]


# ─── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await leads.init_leads_db()
    await analytics_store.init_analytics_db()
    def cleanup_loop():
        while True:
            time.sleep(300)
            _cleanup_sessions()
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    yield
    await database.close_db()


app = FastAPI(title="M.A.T.I.A.S. API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def protect_sensitive_routes(request: Request, call_next):
    """Evita que conversaciones, leads e IP queden expuestos públicamente."""
    content_length = request.headers.get("content-length", "0")
    if content_length.isdigit() and int(content_length) > 65536:
        return Response(content='{"detail":"Solicitud demasiado grande"}', status_code=413, media_type="application/json")

    client_ip = _get_client_ip(request)
    rate_limits = {
        "/api/chat": (20, "chat"),
        "/api/presentacion": (20, "presentacion"),
        "/api/presentacion/event": (120, "presentacion_event"),
        "/api/session/new": (30, "session"),
        "/api/analytics/pageview": (120, "analytics"),
        "/api/analytics/event": (120, "analytics"),
    }
    if request.method == "POST" and request.url.path in rate_limits:
        limit, bucket = rate_limits[request.url.path]
        if not _allow_request(client_ip, bucket, limit):
            return Response(content='{"detail":"Demasiadas solicitudes"}', status_code=429, media_type="application/json")

    sensitive_prefixes = (
        "/api/operations/status",
        "/api/interactions/recent",
        "/api/interactions/stats",
        "/api/interactions/session/",
        "/api/leads",
        "/api/analytics/pageviews",
        "/api/analytics/visitors",
        "/api/analytics/journey/",
        "/api/analytics/ip/",
        "/api/analytics/conversions",
        "/api/analytics/dashboard",
        "/api/presentacion/stats",
        "/api/presentacion/evaluate",
        "/api/admin/",
    )
    if request.url.path.startswith(sensitive_prefixes):
        provided = request.headers.get("X-Admin-Token", "")
        if not ADMIN_TOKEN:
            return Response(content='{"detail":"Administración no configurada"}', status_code=503, media_type="application/json")
        if not hmac.compare_digest(provided, ADMIN_TOKEN):
            return Response(content='{"detail":"No autorizado"}', status_code=401, media_type="application/json")
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://([a-z0-9-]+\.)?(wixsite\.com|wixstudio\.io)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    agent: str
    build_sha: str


class AnalyticsPageView(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    referrer: Optional[str] = Field(default=None, max_length=2048)
    source: Optional[str] = Field(default=None, max_length=100)
    utm_source: Optional[str] = Field(default=None, max_length=200)
    utm_medium: Optional[str] = Field(default=None, max_length=200)
    utm_campaign: Optional[str] = Field(default=None, max_length=200)


class AnalyticsEvent(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=100)
    element: Optional[str] = Field(default=None, max_length=500)
    url: Optional[str] = Field(default=None, max_length=2048)
    metadata: Optional[str] = Field(default=None, max_length=4000)

# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        agent="M.A.T.I.A.S.",
        build_sha=os.getenv("RENDER_GIT_COMMIT", "unknown"),
    )


@app.get("/api/operations/status")
async def operations_status():
    """Estado operativo sin exponer datos personales ni secretos."""
    analytics = await analytics_store.get_analytics_dashboard()
    automation = await leads.get_automation_status()
    return {
        "status": "ok",
        "database": "postgresql" if await database._get_pg_pool() else "unavailable",
        "model": MODEL_ID,
        "build_sha": os.getenv("RENDER_GIT_COMMIT", "unknown"),
        "meeting_url_configured": bool(MEETING_URL),
        "email_configured": bool(os.getenv("ZOHO_APP_PASSWORD")),
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and OSCAR_CHAT_ID),
        "analytics": analytics,
        "automation": automation,
    }


@app.post("/api/session/new", response_model=SessionResponse)
async def new_session(request: Request):
    sid = str(uuid.uuid4())
    with sessions_lock:
        sessions[sid] = Session(sid)

    # Trackear IP por nueva sesión
    client_ip = _get_client_ip(request)
    if _check_ip_abuse(client_ip, sid):
        asyncio.ensure_future(_send_abuse_alert(client_ip, len(ip_tracker.get(client_ip, {}).get("sessions", set())), sid))

    return SessionResponse(session_id=sid)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    with sessions_lock:
        if session_id in sessions:
            del sessions[session_id]
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    lock_key = req.session_id or f"new:{_get_client_ip(request)}"
    with sessions_lock:
        request_lock = session_request_locks.setdefault(lock_key, asyncio.Lock())
    async with request_lock:
        return await _chat_impl(req, request)


async def _chat_impl(req: ChatRequest, request: Request):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")
    if len(req.message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=413, detail="El mensaje excede el tamaño permitido")

    # ── Detección de abuso por IP ──
    client_ip = _get_client_ip(request)
    sid = req.session_id

    with sessions_lock:
        session = sessions.get(sid) if sid else None

    # Reconstruir contexto desde PostgreSQL después de reinicios o despliegues.
    if not session and sid:
        persisted = await database.get_session_interactions(sid, MAX_HISTORY)
        if persisted:
            session = Session(sid)
            for item in reversed(persisted):
                session.add_message(item["role"], item["content"])

    if not session:
        sid = str(uuid.uuid4())
        session = Session(sid)
    assert sid is not None
    with sessions_lock:
        sessions[sid] = session

    # Trackear IP y verificar umbral de abuso
    if _check_ip_abuse(client_ip, sid):
        asyncio.ensure_future(_send_abuse_alert(client_ip, len(ip_tracker.get(client_ip, {}).get("sessions", set())), sid))

    session.add_message("user", req.message.strip())
    await database.log_interaction(sid, "user", req.message.strip(), MODEL_ID, "web")

    # Persistencia sincrónica: nunca responder sin haber guardado los datos compartidos.
    await leads.save_lead(sid, req.message.strip(), ip=client_ip)

    meeting_terms = ("agendar", "agenda", "reunión", "reunion", "demo", "cita", "calendario")
    if any(term in req.message.lower() for term in meeting_terms):
        content = (
            "Puedes elegir directamente un horario disponible en el calendario de Oscar. "
            f"La invitación y el enlace de reunión se confirman automáticamente: {MEETING_URL} "
            "Si me compartes tu nombre, empresa, correo y WhatsApp, Amelia también te acompaña con la coordinación."
        )
        session.add_message("assistant", content)
        await database.log_interaction(sid, "assistant", content, MODEL_ID, "web")
        return ChatResponse(reply=content, session_id=sid)

    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key no configurada")

    try:
        import knowledge_base

        context = knowledge_base.search_relevant(req.message.strip(), max_chars=6000)
        model_messages = [dict(message) for message in session.messages]
        if context:
            model_messages[-1]["content"] = (
                "[CONTEXTO INTERNO VERIFICADO — úsalo como fuente y no lo cites literalmente]\n"
                f"{context}\n[/CONTEXTO INTERNO VERIFICADO]\n\n"
                f"PREGUNTA DEL VISITANTE: {req.message.strip()}"
            )
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL_ID,
                    "messages": model_messages,
                    "temperature": TEMPERATURE,
                    "max_tokens": MAX_TOKENS,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Error del modelo: {e.response.text[:500]}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Error de conexion con DeepSeek: {str(e)}")

    content = data["choices"][0]["message"]["content"]
    session.add_message("assistant", content)
    await database.log_interaction(sid, "assistant", content, MODEL_ID, "web")

    return ChatResponse(reply=content, session_id=sid)


# ─── Reporting endpoints (para Amelia) ─────────────────────────────────────


@app.get("/api/interactions/recent")
async def recent_interactions(limit: int = 50):
    rows = await database.get_recent_interactions(limit)
    return {"total": len(rows), "interactions": rows}


@app.get("/api/interactions/stats")
async def interaction_stats():
    total = await database.get_total_count()
    sessions = await database.get_sessions(50)
    return {"total_interactions": total, "active_sessions": len(sessions), "sessions": sessions}


@app.get("/api/interactions/session/{session_id}")
async def session_interactions(session_id: str, limit: int = 50):
    rows = await database.get_session_interactions(session_id, limit)
    return {"session_id": session_id, "total": len(rows), "interactions": rows}


# ─── Analytics tracking endpoints ─────────────────────────────────────────


@app.post("/api/analytics/pageview")
async def track_pageview(req: AnalyticsPageView, request: Request):
    ua = request.headers.get("User-Agent", "")
    referrer = req.referrer or request.headers.get("Referer", "")
    country = request.headers.get("CF-IPCountry") or request.headers.get("X-Vercel-IP-Country") or "unknown"
    client_ip = _get_client_ip(request)
    # Determinar la fuente de tráfico
    source = req.utm_source or req.source or ""
    if not source and referrer:
        source = referrer  # fallback: dominio de referencia
    await analytics_store.log_page_view(req.session_id, req.url, referrer, ua, country, source=source, ip=client_ip)
    return {"status": "ok"}


@app.post("/api/analytics/event")
async def track_event(req: AnalyticsEvent, request: Request):
    client_ip = _get_client_ip(request)
    await analytics_store.log_event(req.session_id, req.event_type, req.element or "", req.url or "", req.metadata, ip=client_ip)
    return {"status": "ok"}


# ─── Analytics reporting endpoints (para Amelia) ──────────────────────────


@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    data = await analytics_store.get_analytics_dashboard()
    return data


@app.get("/api/analytics/pageviews")
async def analytics_pageviews(limit: int = 50):
    rows = await analytics_store.get_recent_pageviews(limit)
    return {"total": len(rows), "pageviews": rows}


@app.get("/api/analytics/visitors")
async def analytics_visitors(limit: int = 50):
    rows = await analytics_store.get_visitor_sessions(limit)
    return {"total": len(rows), "visitors": rows}


# ─── Leads endpoint (para Amelia) ──────────────────────────────────────────

@app.get("/api/leads")
async def get_leads(limit: int = 50):
    rows = await leads.get_all_leads(limit)
    count = await leads.get_lead_count()
    return {"total": count, "leads": rows}


# ─── Journey endpoint — reconstruye el camino completo de una sesión ──────

@app.get("/api/analytics/journey/{session_id}")
async def get_session_journey(session_id: str):
    """Reconstruye el journey completo de una sesión: pageviews, eventos, lead, sesiones hermanas (misma IP)."""
    pageviews = await analytics_store.get_page_views_by_session(session_id)
    events = await analytics_store.get_events_by_session(session_id)
    lead_data = await leads.get_lead_by_session(session_id)

    # Buscar sesiones hermanas (misma IP)
    ip = ""
    if pageviews:
        ip = pageviews[0].get("ip", "")
    elif lead_data:
        ip = lead_data.get("ip", "")

    sibling_sessions = await analytics_store.get_sessions_by_ip(ip) if ip else []

    # Construir timeline unificado
    timeline = []
    for pv in pageviews:
        timeline.append({"type": "pageview", "timestamp": pv.get("timestamp", ""), "url": pv.get("url", ""),
                         "device": pv.get("device_type", ""), "browser": pv.get("browser", ""),
                         "country": pv.get("country", ""), "source": pv.get("source", "")})
    for ev in events:
        timeline.append({"type": "event", "timestamp": ev.get("timestamp", ""), "event": ev.get("event_type", ""),
                         "element": ev.get("element", ""), "url": ev.get("url", "")})

    timeline.sort(key=lambda x: x.get("timestamp", ""))

    # ¿Hubo conversión?
    converted = any(ev.get("event_type") == "demo_click" for ev in events)

    return {
        "session_id": session_id,
        "ip": ip,
        "total_pageviews": len(pageviews),
        "total_events": len(events),
        "converted": converted,
        "lead": lead_data,
        "timeline": timeline,
        "sibling_sessions": [{"session_id": s.get("session_id", ""), "first_seen": s.get("first_seen", ""),
                              "last_seen": s.get("last_seen", ""), "page_views": s.get("page_views", 0),
                              "events": s.get("events", 0), "country": s.get("country", ""),
                              "device": s.get("device_type", ""), "browser": s.get("browser", "")}
                             for s in sibling_sessions if s.get("session_id") != session_id],
    }


@app.get("/api/analytics/ip/{ip}")
async def get_ip_history(ip: str):
    """Historial completo de una IP: sesiones, pageviews y leads capturados."""
    sessions = await analytics_store.get_sessions_by_ip(ip)
    pageviews = await analytics_store.get_page_views_by_ip(ip)
    leads_list = await leads.get_leads_by_ip(ip)

    return {
        "ip": ip,
        "total_sessions": len(sessions),
        "total_pageviews": len(pageviews),
        "leads_capturados": len(leads_list),
        "sessions": [dict(s) for s in sessions],
        "leads": leads_list,
    }


@app.get("/api/analytics/conversions")
async def get_conversions(dias: int = 7):
    """Lista sesiones que hicieron demo_click (agendaron reunión)."""
    conversions = await analytics_store.get_conversions(dias)
    return {"total": len(conversions), "dias": dias, "conversions": conversions}


# ─── Agente de Presentaciones — RAG sobre conocimiento interno ──────────

from pydantic import BaseModel as PydanticBase

class PresentacionRequest(PydanticBase):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="presentacion", max_length=100)
    name: str = Field(default="Invitado", max_length=100)
    slide: int = Field(default=-1, ge=-1, le=50)  # índice de diapositiva actual (0-based)

class PresentacionResponse(PydanticBase):
    reply: str
    session_id: str
    source: str = "conocimiento_interno"
    sources: list[str] = Field(default_factory=list)

AGENDA_URL = "https://calendar.app.google/up2iyv5hJkJpRJta9"
AGENDA_CTA = (
    "Si quieres más información o ver cómo esto aplica a tu cartera, "
    f"puedes separar una reunión acá:\n{AGENDA_URL}"
)
FALLBACK_REPLY = (
    "Puedo orientarte sobre riesgo de crédito, los modelos de M.A.T.I.A.S. y los servicios de Akaike. "
    "Cuéntame qué te interesa y te guío.\n\n"
    f"Si quieres conocer más, agenda una reunión aquí:\n{AGENDA_URL}"
)

PRESENTACION_SYSTEM = (
    "Eres M.A.T.I.A.S., el asistente comercial de Akaike Credit Risk Solutions. "
    "Tu objetivo es captar el interés del prospecto y llevarlo a agendar una reunión. "
    "NO eres un ingeniero ni un consultor técnico: eres un vendedor que conoce el valor del producto.\n\n"
    "REGLAS DE ORO:\n"
    "1. Habla en lenguaje de negocio: qué problema resuelve Akaike, qué beneficio obtiene el cliente y por qué somos diferentes.\n"
    "2. NUNCA des detalles técnicos profundos: sin paso a paso de construcción, fórmulas, pesos, calibración, métricas de modelo (GINI, KS, WOE, IV, PD, LGD, EAD), arquitectura interna ni metodología detallada.\n"
    "3. Si piden profundizar en lo técnico, da un resumen general de valor y redirige a la agenda.\n"
    "4. PROHIBIDO inferir o inventar. Solo información del contexto disponible.\n"
    "5. ZERO-PII: nunca nombres de autores, clientes, empresas terceras, asistentes ni personas naturales.\n"
    "6. SIEMPRE cierra tu respuesta con una llamada a la acción para agendar o recibir más información.\n"
    "7. Cuando el prospecto muestre interés o pida reunión, demo o detalle, ofrece únicamente: https://calendar.app.google/up2iyv5hJkJpRJta9\n"
    "8. NUNCA inventes emails ni telefonos.\n\n"
    "ESTILO: Respuestas cortas y persuasivas, máximo 120 palabras y dos párrafos cortos. "
    "NUNCA empieces con 'Claro' ni 'Por supuesto'. Ve al grano. "
    "NUNCA uses markdown ni HTML. Las URLs en su propia línea.\n"
)

PUBLIC_BLOCKED_NAMES = (
    "Amazon Web Services", "AWS", "MassChallenge", "StartupAndes", "Colombia Fintech",
    "DataCrédito", "Datacredito", "Experian", "TransUnion", "Claro", "Upstart",
)


def _sanitize_public_reply(text: str) -> str:
    """Última barrera determinística para el widget público."""
    clean = re.sub(r"<[^>]+>", "", text or "")
    clean = clean.replace("**", "").replace("__", "")
    clean = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[correo omitido]", clean)
    clean = re.sub(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", "[teléfono omitido]", clean)
    for name in PUBLIC_BLOCKED_NAMES:
        clean = re.sub(
            r"(?<![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9])" + re.escape(name) + r"(?![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9])",
            "una fuente autorizada",
            clean,
            flags=re.IGNORECASE,
        )
    clean = re.sub(r"(?i)Fuente\s*:\s*[^.\n]{3,120}", "Fuente: Credit Risk Papers", clean)
    clean = re.sub(
        r"\b(?:[Ss]egún|[Aa]utor(?:a|es)?|[Tt]rabajo(?: aplicado)? de)\s+"
        r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ'-]+){1,3}",
        "según la fuente",
        clean,
    )
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", clean) if part.strip()][:2]
    limited: list[str] = []
    word_count = 0
    for paragraph in paragraphs:
        accepted: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            sentence_words = sentence.split()
            if word_count + len(sentence_words) > 120:
                break
            accepted.append(sentence)
            word_count += len(sentence_words)
        if accepted:
            limited.append(" ".join(accepted))
    if not limited and paragraphs:
        limited = [" ".join(paragraphs[0].split()[:120]).rstrip(".,;:") + "."]
    return "\n\n".join(limited).strip()

@app.post("/api/presentacion")
async def presentacion_chat(req: PresentacionRequest, response: Response, request: Request):
    import oscar_graph_runtime

    # Extraer IP
    client_ip = _get_client_ip(request)
    client_ua = request.headers.get("User-Agent", "")

    # LÍMITE DE CUOTA: evita conversaciones indefinidas que consumen tokens.
    if not _consume_chat_quota(client_ip):
        quota_reply = (
            "Has superado tu cuota de chat de esta sesión. "
            "Si quieres conocer más, agenda una reunión aquí:\n" + AGENDA_URL
        )
        return PresentacionResponse(reply=quota_reply, session_id=req.session_id, source="cuota")

    # Texto de cada diapositiva
    slides = {
        0: "Portada: Akaike Credit Risk Solutions. Inteligencia Artificial para credito, entrenada con sus datos. www.akaike.co",
        1: "El Impacto: aumento en la tasa de aprobacion con modelos de IA y reduccion en la tasa de morosidad. Fuente: material autorizado de la presentación.",
        2: "Nosotros: Somos expertos en el desarrollo de modelos de Riesgo de Credito con IA. Optimizamos la cartera, reducimos la morosidad y mejoramos la rentabilidad de entidades en distintos sectores.",
        3: "El Problema: las perdidas por mora se relacionan con una mala evaluacion de riesgo crediticio. Por eso nuestros modelos se entrenan con los datos de la cartera. Fuente: Credit Risk Papers.",
        4: "La Solucion: Una metodologia en cinco pasos. Incremento esperado del ROI: 5:1. PASO 1 - Analisis forense de la informacion: entender que datos tiene la entidad y como se toman las decisiones hoy. PASO 2 - Curacion y transformacion de datos: limpiar, unificar y preparar las fuentes internas y externas. PASO 3 - Ingenieria de variables: crear variables predictivas con poder discriminante real. PASO 4 - Entrenamiento del modelo: la IA aprende patrones de riesgo de los datos historicos. PASO 5 - Implementacion y monitoreo: el modelo se despliega en produccion con seguimiento continuo. Esta metodologia se ha refinado durante 19 anos de experiencia con mas de 250 proyectos en 16 entidades.",
        5: "El Producto - M.A.T.I.A.S.: Modelo Analitico Transformador en Inteligencias Artificiales Scoring. Un API de decision que recibe parametros del cliente, consulta fuentes autorizadas y responde aprobado o rechazado. Las calificaciones del modelo no incluyen el costo de consultas a centrales de riesgo. Cada entidad debe tener su propio contrato con el buro de credito.",
        6: "Capacidades: Una IA, multiples posibilidades. M.A.T.I.A.S. se entrena para originacion, comportamiento, cobranza y analisis conversacional. Credit Scoring, Behaviour Scoring, Collection Scoring, Copilot.",
        7: "Experiencia: +250 modelos y proyectos, 16+ entidades aliadas. Implementacion de software para credito y Credit Scoring personalizado.",
        8: "Fundador: CEO y fundador de Akaike. Economista con posgrado en Riesgos Financieros.",
        9: "Representantes regionales: Presencia en Centroamerica, Ecuador, Colombia y Mexico.",
        10: "Planes: Starter, Scale, Corporate, Enterprise Pro. Cada plan incluye M.A.T.I.A.S. Copilot con diferentes niveles de usuarios y capacidad.",
        11: "Cierre: Es hora de que su compania destaque con Inteligencia Propia. Agenda oficial: https://calendar.app.google/up2iyv5hJkJpRJta9",
    }

    # CONTEXTO PRIMARIO: solo si la consulta pertenece al dominio o refiere a la diapositiva.
    slide_allowed = oscar_graph_runtime.is_domain_question(req.message) or oscar_graph_runtime.is_slide_followup(req.message)
    slide_text = slides.get(req.slide, "") if slide_allowed else ""
    
    # DETECCIÓN DE CONTACTO: responder directo sin LLM
    contacto_keywords = ["asesor", "demo", "reunión", "reunion", "contacto", "contactar",
                        "comuníqueme", "comuniqueme", "hablar con", "llamar", "cita",
                        "agendar", "agenda", "calendario", "whatsapp"]
    if any(re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", req.message, re.IGNORECASE) for kw in contacto_keywords):
        contact_reply = AGENDA_CTA
        try:
            await database.log_presentation_event(
                session_id=req.session_id,
                event_type="question",
                slide=req.slide if req.slide >= 0 else None,
                data={"question": req.message, "reply": contact_reply},
                ip=client_ip,
                user_agent=client_ua,
            )
        except Exception:
            pass
        return PresentacionResponse(
            reply=contact_reply,
            session_id=req.session_id,
            source="agenda",
        )

    # DETECCIÓN DE PROFUNDIZACIÓN TÉCNICA: redirigir a reunión, sin detalles de modelado.
    tecnico_frases = [
        "paso a paso", "como se construye", "como construir", "construirlo", "construir un",
        "como debo constru", "formula", "formulas", "pesos", "calibracion", "calibrar",
        "backtesting", "algoritmo", "segmentacion", "bining", "binning", "matriz de confusion",
        "modelo experto", "modelo hibrido", "modelo propio", "weight of evidence",
    ]
    tecnico_siglas = ["gini", "ks", "woe", "iv", "auc", "roc", "logit", "pd", "lgd", "ead"]
    es_tecnico = any(frase in req.message.lower() for frase in tecnico_frases) or any(
        re.search(r"(?<!\w)" + re.escape(sigla) + r"(?!\w)", req.message, re.IGNORECASE)
        for sigla in tecnico_siglas
    )
    if es_tecnico:
        tecnico_reply = (
            "Ese detalle lo diseñamos a la medida de tu operación, así que prefiero mostrártelo "
            "en una reunión donde revisamos tu caso concreto. " + AGENDA_CTA
        )
        try:
            await database.log_presentation_event(
                session_id=req.session_id,
                event_type="question",
                slide=req.slide if req.slide >= 0 else None,
                data={"question": req.message, "reply": tecnico_reply},
                ip=client_ip,
                user_agent=client_ua,
            )
        except Exception:
            pass
        return PresentacionResponse(
            reply=tecnico_reply,
            session_id=req.session_id,
            source="agenda",
        )

    if slide_text:
        slide_context = f"[DIAPOSITIVA ACTUAL - texto visible]\n{slide_text}\n[/DIAPOSITIVA ACTUAL]\n\n"
    else:
        slide_context = ""

    # CONTEXTO SECUNDARIO: grafo público autorizado
    graph_context, graph_sources = oscar_graph_runtime.search(req.message, max_chars=9000)

    full_context = slide_context
    if graph_context:
        full_context += f"\n[GRAFO PÚBLICO CON PROCEDENCIA]\n{graph_context}\n[/GRAFO PÚBLICO CON PROCEDENCIA]"

    if not full_context.strip():
        return PresentacionResponse(
            reply=FALLBACK_REPLY,
            session_id=req.session_id,
            source="sin_fuente",
        )

    # Llamar a DeepSeek
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return PresentacionResponse(
            reply="Servicio no disponible.\n" + AGENDA_URL,
            session_id=req.session_id,
            source="sin_fuente",
        )

    response_source = "grafo_publico" if graph_context else "diapositiva"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": PRESENTACION_SYSTEM + "\n\n" + oscar_graph_runtime.style_prompt()},
                        {"role": "user", "content": f"{full_context}\n\nPREGUNTA DEL USUARIO: {req.message}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
            )
            r.raise_for_status()
            data = r.json()
            reply = data["choices"][0]["message"]["content"]
    except Exception:
        reply = "No pude procesar tu consulta en este momento.\n" + AGENDA_URL
        response_source = "sin_fuente"

    reply = _sanitize_public_reply(reply)

    # CONVERSIÓN: toda respuesta sustantiva cierra siempre con la llamada a agendar.
    if response_source in {"grafo_publico", "diapositiva"} and AGENDA_URL not in reply:
        reply = reply.rstrip() + "\n\n" + AGENDA_CTA

    # Registrar pregunta en BD
    await database.log_presentation_event(
        session_id=req.session_id,
        event_type="question",
        slide=req.slide if req.slide >= 0 else None,
        data={"question": req.message, "reply": reply},
        ip=client_ip,
        user_agent=client_ua,
    )

    return PresentacionResponse(reply=reply, session_id=req.session_id, source=response_source, sources=graph_sources[:5])


# ─── Eventos de presentación ──────────────────────────────────────────────

class PresentacionEvent(PydanticBase):
    session_id: str
    event_type: str  # 'slide_view' o 'slide_duration'
    slide: Optional[int] = None
    seconds: Optional[float] = None  # para slide_duration
    name: str = "Invitado"

@app.post("/api/presentacion/event")
async def presentacion_event(req: PresentacionEvent, request: Request):
    response = Response()
    response.headers["Access-Control-Allow-Origin"] = "*"
    
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    data = {}
    if req.seconds is not None:
        data["seconds"] = req.seconds
    if req.name:
        data["name"] = req.name
    
    await database.log_presentation_event(
        session_id=req.session_id,
        event_type=req.event_type,
        slide=req.slide,
        data=data,
        ip=ip,
        user_agent=ua,
    )
    return {"ok": True}

# ─── Stats de presentación ────────────────────────────────────────────────

@app.get("/api/presentacion/stats")
async def presentacion_stats(days: int = 7):
    try:
        return await database.get_presentation_stats(days=days)
    except Exception as e:
        return {"period_days": days, "total_questions": 0, "unique_sessions": 0,
                "avg_questions_per_session": 0, "active_sessions_today": 0,
                "questions_today": 0, "questions_by_slide": [],
                "duration_by_slide": [], "recent_questions": [],
                "note": f"DB no disponible. Se registraran datos cuando la presentacion se use. ({str(e)[:100]})"}


# ─── Evaluación de calidad ────────────────────────────────────────────────

@app.get("/api/presentacion/evaluate")
async def presentacion_evaluate(days: int = 1):
    """Evalua la calidad de las respuestas del agente de presentacion.
    Compara cada respuesta contra el knowledge base y asigna puntaje 1-5.
    """
    import knowledge_base
    
    stats = await database.get_presentation_stats(days=days)
    questions = stats.get("recent_questions", [])
    
    if not questions:
        return {"evaluated": 0, "message": "No hay preguntas para evaluar"}
    
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"error": "DEEPSEEK_API_KEY no configurada"}
    
    evaluations = []
    scores = []
    
    async with httpx.AsyncClient(timeout=120) as client:
        for q in questions:
            question_text = q.get("question", "")
            actual_reply = q.get("reply", "")
            slide_num = q.get("slide", -1)
            
            # Buscar en el KB la respuesta ideal
            kb_context = knowledge_base.search_relevant(question_text, slide_num, max_chars=6000)
            
            if not kb_context:
                evaluations.append({
                    "question": question_text[:120],
                    "slide": slide_num,
                    "score": None,
                    "issue": "Sin contexto en KB para evaluar",
                })
                continue
            
            # Pedir a DeepSeek que evalue
            eval_prompt = (
                "Eres un auditor de calidad de Akaike Credit Risk Solutions. Evalua esta respuesta del bot de presentaciones.\n\n"
                f"PREGUNTA DEL USUARIO: {question_text}\n\n"
                f"RESPUESTA DEL BOT: {actual_reply}\n\n"
                f"CONTEXTO DE LA PRESENTACION (fuente de verdad):\n{kb_context}\n\n"
                "EVALUA (responde SOLO en este formato JSON, sin markdown):\n"
                '{"score": 4, "accuracy": "alta|media|baja", "issues": ["problema 1", "problema 2"], '
                '"suggestion": "mejora concreta y accionable", "missing": "lo que falto decir"}'
                "\n\n"
                "CRITERIOS de scoring (1-5):\n"
                "5 = Respuesta perfecta, precisa, basada en datos reales de Akaike, concisa, sin alucinaciones\n"
                "4 = Correcta pero le falto profundidad o contexto relevante del KB\n"
                "3 = Parcialmente correcta, omite informacion importante del KB\n"
                "2 = Tiene errores factuales o alucina datos que no estan en el KB\n"
                "1 = Completamente equivocada, inventa, o contradice el KB\n\n"
                "SOLO responde el JSON. Nada mas."
            )
            
            try:
                r = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": eval_prompt}],
                        "temperature": 0.1,
                        "max_tokens": 300,
                    },
                )
                data = r.json()
                raw = data["choices"][0]["message"]["content"].strip()
                # Limpiar markdown
                raw = raw.replace("```json", "").replace("```", "").strip()
                
                import json as _json
                try:
                    ev = _json.loads(raw)
                except Exception:
                    # Intentar extraer JSON
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    ev = _json.loads(match.group()) if match else {"score": None, "error": raw[:100]}
                
                score = ev.get("score")
                if score:
                    scores.append(score)
                
                evaluations.append({
                    "question": question_text[:150],
                    "slide": slide_num,
                    "score": score,
                    "accuracy": ev.get("accuracy", ""),
                    "issues": ev.get("issues", []),
                    "suggestion": ev.get("suggestion", ""),
                    "missing": ev.get("missing", ""),
                })
            except Exception as e:
                evaluations.append({
                    "question": question_text[:120],
                    "slide": slide_num,
                    "score": None,
                    "error": str(e)[:100],
                })
    
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    low_scores = [e for e in evaluations if e.get("score") and e["score"] <= 3]
    
    return {
        "evaluated": len(evaluations),
        "average_score": avg_score,
        "score_distribution": {
            "5": len([s for s in scores if s == 5]),
            "4": len([s for s in scores if s == 4]),
            "3": len([s for s in scores if s == 3]),
            "2": len([s for s in scores if s == 2]),
            "1": len([s for s in scores if s == 1]),
        },
        "needs_improvement": len(low_scores),
        "improvements": [
            {
                "question": e["question"],
                "score": e["score"],
                "issue": e.get("issues", [None])[0] if e.get("issues") else "",
                "suggestion": e.get("suggestion", ""),
            }
            for e in low_scores[:5]
        ],
        "all_evaluations": evaluations,
    }


# ─── Diagnostico leads ────────────────────────────────────────────────────────

@app.get("/api/leads/debug")
async def leads_debug():
    dsn = leads.DATABASE_URL
    masked = dsn[:20] + "***" + dsn[-15:] if len(dsn) > 40 else ("VACIO" if not dsn else dsn[:10] + "***")
    return {
        "database_url_set": bool(dsn),
        "url_preview": masked,
        "extract_test1": leads._extract_lead_data("ogutimo82@gmail.com Oscar Akaike"),
        "extract_test2": leads._extract_lead_data("test@example.com"),
    }


# ─── Security: Enable RLS ─────────────────────────────────────────────────────

@app.post("/api/admin/enable-rls")
async def admin_enable_rls():
    result = await database.enable_rls_on_all_tables()
    return result


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
