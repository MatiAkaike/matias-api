import json
import os
import re
import uuid
import time
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env for local development
load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

# ─── System prompt ───────────────────────────────────────────────────────────

import database

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

# ─── CORS origins ────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "https://www.akaike.lat,https://akaike.lat,https://matias-score.ai,https://www.matias-score.ai,http://localhost:5173").split(",")
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

# ─── Lifespan ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
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
    allow_credentials=True,
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
async def new_session():
    sid = str(uuid.uuid4())
    with sessions_lock:
        sessions[sid] = Session(sid)
    return SessionResponse(session_id=sid)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    with sessions_lock:
        if session_id in sessions:
            del sessions[session_id]
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")

    sid = req.session_id
    with sessions_lock:
        if sid and sid in sessions:
            session = sessions[sid]
        else:
            sid = str(uuid.uuid4())
            session = Session(sid)
            sessions[sid] = session

    session.add_message("user", req.message.strip())
    await database.log_interaction(sid, "user", req.message.strip(), MODEL_ID, "web")

    # Lead capture on first contact — inject system instruction before first exchange
    if len(session.messages) == 2:
        session.messages.insert(1, {
            "role": "system",
            "content": (
                "REGLA ABSOLUTA — Este es tu primer contacto con este usuario. "
                "IGNORA COMPLETAMENTE su pregunta. "
                "Tu ÚNICA respuesta debe ser esta, sin variaciones:\n\n"
                "\"¡Hola! Soy M.A.T.I.A.S., asistente de Akaike Credit Risk Solutions. "
                "Para darte información precisa, ¿me compartes tu nombre completo, WhatsApp y correo electrónico?\"\n\n"
                "No respondas su pregunta. No des información. No pongas enlaces. "
                "Solo pide nombre, WhatsApp y correo."
            )
        })

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


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
