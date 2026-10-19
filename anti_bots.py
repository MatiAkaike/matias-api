"""Protección contra bots para el chat y el formulario de la presentación.

1. Prueba de trabajo (al estilo ALTCHA, sin servicios externos): el servidor emite un reto firmado
   (HMAC) y el navegador busca el número cuyo SHA-256 lo resuelve. Cada reto sirve una sola vez y
   vence en 5 minutos. Un visitante tarda menos de un segundo; un bot paga ese costo por cada
   petición.
2. Origen: solo se aceptan peticiones hechas desde akaike.lat.
3. Freno global: tope de respuestas del modelo por hora para todo el sitio.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import deque

MAX_NUMERO = int(os.getenv("PRESENTACION_RETO_MAX", "80000"))
VIGENCIA = 300  # segundos
ORIGENES = {"https://www.akaike.lat", "https://akaike.lat"}
TOPE_HORA = int(os.getenv("PRESENTACION_TOPE_HORA", "240"))


def _secreto() -> bytes:
    propio = os.getenv("PRESENTACION_RETO_SECRET", "")
    if propio:
        return propio.encode()
    admin = os.getenv("MATIAS_ADMIN_TOKEN", "")
    if admin:  # derivado: no expone el token de administración
        return hmac.new(admin.encode(), b"presentacion-reto-v1", hashlib.sha256).digest()
    return _ALEATORIO


_ALEATORIO = secrets.token_bytes(32)
_usados: dict[str, float] = {}
_usados_lock = threading.Lock()
_respuestas: deque[float] = deque()
_respuestas_lock = threading.Lock()


def _firma(salt: str, reto: str, expira: int, emitido: int) -> str:
    return hmac.new(_secreto(), f"{salt}|{reto}|{expira}|{emitido}".encode(), hashlib.sha256).hexdigest()


def emitir_reto() -> dict:
    salt = secrets.token_hex(12)
    numero = secrets.randbelow(MAX_NUMERO)
    emitido = int(time.time())
    expira = emitido + VIGENCIA
    reto = hashlib.sha256(f"{salt}{numero}".encode()).hexdigest()
    return {"algoritmo": "SHA-256", "salt": salt, "reto": reto, "max": MAX_NUMERO,
            "emitido": emitido, "expira": expira, "firma": _firma(salt, reto, expira, emitido)}


def verificar(cabecera: str, edad_minima: int = 0) -> tuple[bool, str]:
    """Valida la cabecera X-Reto (base64 de JSON con salt, reto, emitido, expira, firma y numero)."""
    try:
        d = json.loads(base64.b64decode(cabecera or "", validate=True))
        salt, reto, firma = str(d["salt"]), str(d["reto"]), str(d["firma"])
        emitido, expira, numero = int(d["emitido"]), int(d["expira"]), int(d["numero"])
    except Exception:
        return False, "sin_reto"
    ahora = time.time()
    if not hmac.compare_digest(firma, _firma(salt, reto, expira, emitido)):
        return False, "firma"
    if ahora > expira:
        return False, "vencido"
    if ahora - emitido < edad_minima:
        return False, "rapido"
    if not (0 <= numero <= MAX_NUMERO) or hashlib.sha256(f"{salt}{numero}".encode()).hexdigest() != reto:
        return False, "solucion"
    with _usados_lock:
        for s in [s for s, t in _usados.items() if t < ahora]:
            del _usados[s]
        if salt in _usados:
            return False, "repetido"
        _usados[salt] = expira
    return True, "ok"


def origen_valido(origin: str, referer: str = "") -> bool:
    if origin:
        return origin.rstrip("/") in ORIGENES
    return any(referer.startswith(o + "/") for o in ORIGENES)


def hay_cupo_global() -> bool:
    """Cuenta una respuesta del modelo; False si ya se alcanzó el tope de la última hora."""
    ahora = time.time()
    with _respuestas_lock:
        while _respuestas and ahora - _respuestas[0] > 3600:
            _respuestas.popleft()
        if len(_respuestas) >= TOPE_HORA:
            return False
        _respuestas.append(ahora)
        return True
