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


async def _try_capture_lead(session_id: str, message: str):
    """Attempt to extract and save lead data from a user message."""
    try:
        lead = await leads.save_lead(session_id, message)
        if lead:
            await leads.notify_amelia(lead, session_id, message)
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
    asyncio.ensure_future(_try_capture_lead(sid, req.message.strip()))

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
    await database.log_page_view(req.session_id, req.url, referrer, ua, country)
    return {"status": "ok"}


@app.post("/api/analytics/event")
async def track_event(req: AnalyticsEvent):
    await database.log_event(req.session_id, req.event_type, req.element or "", req.url or "", req.metadata)
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
    "1. El texto de [DIAPOSITIVA ACTUAL] es SOLO un ancla. Usa [CONTEXTO ADICIONAL] para DAR DETALLE.\n"
    "2. Si el usuario pregunta sobre algo que la diapositiva solo menciona, EXPLICALO con el CONTEXTO ADICIONAL.\n"
    "3. NUNCA digas 'no se detalla' o 'solo menciona' si hay informacion en el CONTEXTO ADICIONAL.\n"
    "4. PROHIBIDO inferir o inventar. Solo datos textuales de las fuentes.\n"
    "5. ZERO-PII.\n"
    "6. Si de verdad no hay nada: 'Esa informacion no esta en las presentaciones. Agenda con Oscar: https://calendar.app.google/YhY1KSgjktrRrcBb6'\n"
    "7. Si piden asesor, demo o contacto: 'Agenda con Oscar Gutierrez, CEO de Akaike: https://calendar.app.google/YhY1KSgjktrRrcBb6'\n"
    "8. NUNCA inventes emails ni telefonos.\n\n"
    "ESTILO: Maximo 2 parrafos cortos (2-3 lineas cada uno). Frases directas. Ve al grano. SIN markdown.\n"
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
async def presentacion_chat(req: PresentacionRequest, response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    import knowledge_base

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
                    "max_tokens": 800,
                },
            )
            data = r.json()
            reply = data["choices"][0]["message"]["content"]
    except Exception:
        reply = "No pude procesar tu consulta en este momento. Contactá a Oscar Gutiérrez:\n📧 oscar@akaike.co | 📱 +57 313 412 4795\n📅 https://calendar.app.google/YhY1KSgjktrRrcBb6"

    return PresentacionResponse(reply=reply, session_id=req.session_id)


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
