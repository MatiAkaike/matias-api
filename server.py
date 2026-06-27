import json
import os
import re
import uuid
import time
import threading
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env for local development
load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

# ─── System prompt ───────────────────────────────────────────────────────────

import database
import leads

try:
    from prompt import SYSTEM_PROMPT
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

# ─── Alerta de abuso por IP ───────────────────────────────────────────────────

ABUSE_THRESHOLD = int(os.getenv("ABUSE_SESSION_THRESHOLD", "20"))  # sesiones por IP
ABUSE_COOLDOWN = int(os.getenv("ABUSE_ALERT_COOLDOWN", "3600"))    # segundos entre alertas por IP
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8957187826:AAGzDUwn6iW_olqpJVz2KNpWGybaoF3R8ro")
OSCAR_CHAT_ID = os.getenv("OSCAR_TELEGRAM_CHAT_ID", "8740011589")

# {ip: {"sessions": set(), "last_alert": timestamp}}
ip_tracker: dict[str, dict] = {}
ip_tracker_lock = threading.Lock()

def _get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente (respeta proxies como Render/Cloudflare)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    cf_ip = request.headers.get("CF-Connecting-IP", "")
    if cf_ip:
        return cf_ip
    return request.client.host if request.client else "unknown"


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
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
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


def _cleanup_sessions():
    now = time.time()
    with sessions_lock:
        expired = [sid for sid, s in sessions.items() if now - s.last_access > SESSION_TTL]
        for sid in expired:
            del sessions[sid]


async def _try_capture_lead(session_id: str, message: str, client_ip: str = ""):
    """Attempt to extract and save lead data from a user message."""
    try:
        lead = await leads.save_lead(session_id, message, ip=client_ip)
        if lead:
            # Notificar a Amelia por Telegram
            await leads.notify_amelia(lead, session_id, message)
            # Enviar correo al lead si tiene email
            if lead.get("correo"):
                asyncio.create_task(leads.send_lead_email(lead, session_id))
    except Exception:
        pass

# ─── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await leads.init_leads_db()
    def cleanup_loop():
        while True:
            time.sleep(300)
            _cleanup_sessions()
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    yield


app = FastAPI(title="M.A.T.I.A.S. API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    agent: str


class AnalyticsPageView(BaseModel):
    session_id: str
    url: str
    referrer: Optional[str] = None
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class AnalyticsEvent(BaseModel):
    session_id: str
    event_type: str
    element: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[str] = None

# ─── Routes ──────────────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", agent="M.A.T.I.A.S.")


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
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")

    # ── Detección de abuso por IP ──
    client_ip = _get_client_ip(request)
    sid = req.session_id

    with sessions_lock:
        if sid and sid in sessions:
            session = sessions[sid]
        else:
            sid = str(uuid.uuid4())
            session = Session(sid)
            sessions[sid] = session

    # Trackear IP y verificar umbral de abuso
    if _check_ip_abuse(client_ip, sid):
        asyncio.ensure_future(_send_abuse_alert(client_ip, len(ip_tracker.get(client_ip, {}).get("sessions", set())), sid))

    session.add_message("user", req.message.strip())
    await database.log_interaction(sid, "user", req.message.strip(), MODEL_ID, "web")

    # Lead capture: try to extract contact data from user's message
    asyncio.ensure_future(_try_capture_lead(sid, req.message.strip(), client_ip))

    # Lead capture — elegant hook for contact data (MEJORADO 2026-06-17)
    # En vez de inyectar un system message que confunde al modelo,
    # agregamos un recordatorio claro como prefijo del historial
    if len(session.messages) == 2:
        session.messages[1] = {
            "role": "user",
            "content": (
                "[Instruccion interna para el asistente — NO mostrar al usuario]\n"
                f"Mensaje del usuario: {req.message.strip()}\n\n"
                "RECUERDA: Responde PRIMERO la pregunta del usuario con valor real. "
                "DESPUES, ofrece enviarle informacion adicional y pide sus datos de contacto "
                "(nombre, empresa, cargo, WhatsApp, correo) de forma elegante. "
                "Siempre cierra con CTA de demo."
            )
        }

    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key no configurada")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL_ID,
                    "messages": session.messages,
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
    await database.log_page_view(req.session_id, req.url, referrer, ua, country, source=source, ip=client_ip)
    return {"status": "ok"}


@app.post("/api/analytics/event")
async def track_event(req: AnalyticsEvent, request: Request):
    client_ip = _get_client_ip(request)
    await database.log_event(req.session_id, req.event_type, req.element or "", req.url or "", req.metadata, ip=client_ip)
    return {"status": "ok"}


# ─── Analytics reporting endpoints (para Amelia) ──────────────────────────


@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    data = await database.get_analytics_dashboard()
    return data


@app.get("/api/analytics/pageviews")
async def analytics_pageviews(limit: int = 50):
    rows = await database.get_recent_pageviews(limit)
    return {"total": len(rows), "pageviews": rows}


@app.get("/api/analytics/visitors")
async def analytics_visitors(limit: int = 50):
    rows = await database.get_visitor_sessions(limit)
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
    pageviews = await database.get_page_views_by_session(session_id)
    events = await database.get_events_by_session(session_id)
    lead_data = await leads.get_lead_by_session(session_id)

    # Buscar sesiones hermanas (misma IP)
    ip = ""
    if pageviews:
        ip = pageviews[0].get("ip", "")
    elif lead_data:
        ip = lead_data.get("ip", "")

    sibling_sessions = await database.get_sessions_by_ip(ip) if ip else []

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
    sessions = await database.get_sessions_by_ip(ip)
    pageviews = await database.get_page_views_by_ip(ip)
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
    from datetime import datetime as dt, timedelta
    db = await database._get_sqlite()
    try:
        since = (dt.utcnow() - timedelta(days=dias)).isoformat()
        cursor = await db.execute(
            """SELECT session_id, timestamp, element, url 
               FROM analytics_events 
               WHERE event_type = 'demo_click' AND timestamp >= ? 
               ORDER BY timestamp DESC""",
            (since,)
        )
        conversions = [dict(row) for row in await cursor.fetchall()]

        # Enriquecer con IP y resumen de cada sesión
        enriched = []
        for c in conversions:
            sid = c["session_id"]
            # IP de los pageviews de esa sesión
            cursor2 = await db.execute(
                "SELECT ip, country FROM page_views WHERE session_id = ? LIMIT 1", (sid,)
            )
            pv = await cursor2.fetchone()
            ip = dict(pv)["ip"] if pv else ""
            country = dict(pv)["country"] if pv else ""

            # Contar pageviews
            cursor3 = await db.execute(
                "SELECT COUNT(*) as c FROM page_views WHERE session_id = ?", (sid,)
            )
            pv_count = dict(await cursor3.fetchone())["c"]

            enriched.append({
                "session_id": sid,
                "timestamp": c["timestamp"],
                "url_desde": c["url"] or "",
                "elemento": c["element"] or "",
                "ip": ip,
                "country": country,
                "pageviews_en_sesion": pv_count,
            })

        return {"total": len(enriched), "dias": dias, "conversions": enriched}
    finally:
        await db.close()


# ─── Agente de Presentaciones — RAG sobre conocimiento interno ──────────

from pydantic import BaseModel as PydanticBase

class PresentacionRequest(PydanticBase):
    message: str
    session_id: str = "presentacion"
    name: str = "Invitado"
    slide: int = -1  # índice de diapositiva actual (0-based)

class PresentacionResponse(PydanticBase):
    reply: str
    session_id: str
    source: str = "conocimiento_interno"

PRESENTACION_SYSTEM = (
    "Eres el asistente virtual de Akaike Credit Risk Solutions experto en las presentaciones corporativas. "
    "Conoces en profundidad los 37 documentos de la compañia.\n\n"
    "REGLAS DE ORO:\n"
    "1. Usa TODA la informacion disponible en el contexto para responder con sustancia.\n"
    "2. Si hay [DIAPOSITIVA ACTUAL], conecta tu respuesta con ella.\n"
    "3. NUNCA digas 'no se detalla' o 'solo menciona'. EXPLICA con lo que tengas.\n"
    "4. PROHIBIDO inferir o inventar. Solo datos textuales.\n"
    "5. ZERO-PII.\n"
    "6. Si no hay respuesta: 'Agenda con Oscar Gutierrez, CEO: https://calendar.app.google/YhY1KSgjktrRrcBb6'\n"
    "7. Si piden asesor o demo: 'Agenda con Oscar: https://calendar.app.google/YhY1KSgjktrRrcBb6'\n"
    "8. NUNCA inventes emails ni telefonos.\n\n"
    "ESTILO: Respuestas ultra concisas. NUNCA empieces con 'Claro', 'Por supuesto'. "
    "Ve directo al punto. NUNCA uses markdown ni HTML. "
    "Las URLs en su propia linea.\n"
)

@app.options("/api/presentacion")
async def presentacion_preflight():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
    )


@app.post("/api/presentacion")
async def presentacion_chat(req: PresentacionRequest, response: Response, request: Request):
    response.headers["Access-Control-Allow-Origin"] = "*"
    import knowledge_base

    # Extraer IP
    client_ip = _get_client_ip(request)
    client_ua = request.headers.get("User-Agent", "")

    # Texto de cada diapositiva
    slides = {
        0: "Portada: Akaike Credit Risk Solutions. Inteligencia Artificial para credito, entrenada con sus datos. www.akaike.co",
        1: "El Impacto: aumento en la tasa de aprobacion con modelos de IA. reduccion en la tasa de morosidad. Fuente: Informe de Impacto de IA en Credito - Upstart vs. grandes bancos de EE.UU., Reporte SEC 2024.",
        2: "Nosotros: Somos expertos en el desarrollo de modelos de Riesgo de Credito con IA. Optimizamos la cartera, reducimos la morosidad y mejoramos la rentabilidad de entidades en distintos sectores. Reconocidos por StartupAndes, AWS, MassChallenge, Colombia Fintech.",
        3: "El Problema: de las perdidas por mora se atribuye a una mala evaluacion de riesgo crediticio. Por eso nuestros modelos se entrenan con los datos de la cartera. Fuente: Van Gestel & Baesens - Credit Risk Management: Basic Concepts, 2009. Grafo neuronal vivo.",
        4: "La Solucion: Una metodologia en cinco pasos. Incremento esperado del ROI: 5:1. PASO 1 - Analisis forense de la informacion: entender que datos tiene la entidad y como se toman las decisiones hoy. PASO 2 - Curacion y transformacion de datos: limpiar, unificar y preparar las fuentes internas y externas. PASO 3 - Ingenieria de variables: crear variables predictivas con poder discriminante real. PASO 4 - Entrenamiento del modelo: la IA aprende patrones de riesgo de los datos historicos. PASO 5 - Implementacion y monitoreo: el modelo se despliega en produccion con seguimiento continuo. Esta metodologia se ha refinado durante 19 anos de experiencia con mas de 250 proyectos en 16 entidades.",
        5: "El Producto - M.A.T.I.A.S.: Modelo Analitico Transformador en Inteligencias Artificiales Scoring. Un API de decision que recibe parametros del cliente, consulta fuentes y responde aprobado o rechazado. Consume Datacredito/Experian, TransUnion, Claro, Parafiscales, entre otros. IMPORTANTE: las calificaciones del modelo NO incluyen el costo de la consulta a Datacredito ni a centrales de riesgo. Cada entidad debe tener su propio contrato con el buro de credito.",
        6: "Capacidades: Una IA, multiples posibilidades. M.A.T.I.A.S. se entrena para originacion, comportamiento, cobranza y analisis conversacional. Credit Scoring, Behaviour Scoring, Collection Scoring, Copilot.",
        7: "Experiencia: +250 modelos y proyectos, 16+ entidades aliadas. Implementacion de software para credito y Credit Scoring personalizado.",
        8: "Fundador: Oscar Gutierrez M., CEO y Fundador. Economista con posgrado en Riesgos Financieros. oscar@akaike.co",
        9: "Representantes regionales: Presencia en Centroamerica, Ecuador, Colombia y Mexico. Javier Hidalgo, Ingrid Restrepo, Carlos Rodriguez.",
        10: "Planes: Starter, Scale, Corporate, Enterprise Pro. Cada plan incluye M.A.T.I.A.S. Copilot con diferentes niveles de usuarios y capacidad.",
        11: "Cierre: Es hora de que su compania destaque con Inteligencia Propia. Contacto: Oscar Gutierrez, +57 313 412 4795, oscar@akaike.co",
    }

    # CONTEXTO PRIMARIO: texto de la diapositiva actual
    slide_text = slides.get(req.slide, "")
    
    # DETECCIÓN DE CONTACTO: responder directo sin LLM
    contacto_keywords = ["asesor", "demo", "reunión", "reunion", "contacto", "contactar",
                        "comuníqueme", "comuniqueme", "hablar con", "llamar", "cita",
                        "agendar", "agenda", "calendario", "whatsapp"]
    if any(kw in req.message.lower() for kw in contacto_keywords):
        return PresentacionResponse(
            reply="Agenda directamente con Oscar Gutierrez, CEO de Akaike: https://calendar.app.google/YhY1KSgjktrRrcBb6",
            session_id=req.session_id,
        )
    if slide_text:
        slide_context = f"[DIAPOSITIVA ACTUAL - texto visible]\n{slide_text}\n[/DIAPOSITIVA ACTUAL]\n\n"
    else:
        slide_context = ""

    # CONTEXTO SECUNDARIO: knowledge base
    kb_context = knowledge_base.search_relevant(req.message, req.slide, max_chars=8000)

    full_context = slide_context
    if kb_context:
        full_context += f"[CONTEXTO ADICIONAL]\n{kb_context}\n[/CONTEXTO ADICIONAL]"

    if not full_context.strip():
        return PresentacionResponse(
            reply="Esa información no está en la presentación. Contactá a Oscar Gutiérrez, CEO de Akaike: 📧 oscar@akaike.co | 📱 +57 313 412 4795 | 📅 https://calendar.app.google/YhY1KSgjktrRrcBb6",
            session_id=req.session_id,
        )

    # Llamar a DeepSeek
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return PresentacionResponse(
            reply="Servicio no disponible. Contactá a Oscar: 📧 oscar@akaike.co | 📱 +57 313 412 4795",
            session_id=req.session_id,
        )

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
                        {"role": "system", "content": PRESENTACION_SYSTEM},
                        {"role": "user", "content": f"{full_context}\n\nPREGUNTA DEL USUARIO: {req.message}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
            )
            data = r.json()
            reply = data["choices"][0]["message"]["content"]
    except Exception:
        reply = "No pude procesar tu consulta en este momento. Contactá a Oscar Gutiérrez:\n📧 oscar@akaike.co | 📱 +57 313 412 4795\n📅 https://calendar.app.google/YhY1KSgjktrRrcBb6"

    # Registrar pregunta en BD
    await database.log_presentation_event(
        session_id=req.session_id,
        event_type="question",
        slide=req.slide if req.slide >= 0 else None,
        data={"question": req.message, "reply": reply},
        ip=client_ip,
        user_agent=client_ua,
    )

    return PresentacionResponse(reply=reply, session_id=req.session_id)


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

@app.options("/api/presentacion/event")
async def presentacion_event_preflight():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600",
        }
    )


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


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
