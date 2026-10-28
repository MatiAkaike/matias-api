"""Políticas determinísticas del chat público; los mensajes siguen siendo datos."""
import asyncio
import base64
import binascii
import html
import re
import unicodedata
from urllib.parse import unquote

from starlette.responses import JSONResponse


def normalized_text(text: str) -> str:
    """Normaliza para inspección, sin modificar los datos originales persistidos."""
    text = unicodedata.normalize('NFKC', html.unescape(text or ''))
    text = ''.join(char for char in text if unicodedata.category(char) != 'Cf')
    text = ''.join(char for char in unicodedata.normalize('NFKD', text) if not unicodedata.combining(char))
    return text.casefold()


INJECTION_PATTERNS = (
    r'\b(?:ignore|disregard|override)\b.{0,100}\b(?:instructions|rules|system prompt)\b',
    r'\b(?:ignora|ignorar|omite|olvida|desobedece)\b.{0,100}\b(?:instrucciones|reglas|prompt)\b',
    r'\b(?:print|show|reveal|repeat|translate|encode|expose)\b.{0,100}\b(?:system|developer)\s+(?:prompt|instructions|message)\b',
    r'\b(?:muestra|revela|imprime|repite|traduce|codifica|extrae)\b.{0,100}\b(?:prompt|instrucciones internas|instrucciones de sistema)\b',
    r'\b(?:muestra|revela|imprime|entrega|extrae|show|reveal|print|give)\b.{0,100}\b(?:credenciales|secretos|mensaje del sistema|system prompt|credentials|secrets)\b',
    r'<\|(?:im_start|system|endoftext)\|>|\[/?INST\]|<<\s*SYS\s*>>',
    r'\bor\s+[\x27\"]?1[\x27\"]?\s*=\s*[\x27\"]?1\b',
    r'\bunion\s+(?:all\s+)?select\b|\b(?:drop|truncate)\s+table\b',
)


COMMERCIAL_PATTERNS = (
    r'(?<!sin )\b(?:precio|precios|tarifa|tarifas|descuento|descuentos|cotizacion|pricing|prices|fees)\b',
    r'\b(?:cual(?:es)?(?:\s+es|\s+son)?|que)\s+(?:el\s+|los\s+)?(?:costo|costos|coste)\b',
    r'\b(?:costo|costos|coste)\b.{0,30}\b(?:servicio|matias|akaike|mensual|anual|suscripcion|licencia)\b',
    r'\bcuanto\s+(?:cuesta|cuestan|vale|valen|cobran|pago|pagar)\b',
    r'\b(?:cotiz\w*|quotation|quote|prices?)\b',
    r'\b(?:necesito|solicito|quiero|dame|enviame)\s+(?:(?:un|el)\s+)?presupuest\w*\b',
    r'\bpresupuest\w*\s+(?:(?:de|del|para|por)\s+)?(?:akaike|matias|credit\s+(?:agent|score)|copilot|signals|flows|contratar|implementar)\b',
    r'\bpricing\b',
)


def inspection_text(text: str) -> str:
    """Inspecciona codificaciones comunes con trabajo acotado; nunca las ejecuta."""
    variants = [normalized_text(text), normalized_text(unquote(text))]
    for token in re.findall(r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{12,}={0,2}', text or '')[:12]:
        try:
            decoded = base64.b64decode(token + '=' * (-len(token) % 4), validate=True).decode('utf-8')
        except (binascii.Error, UnicodeError, ValueError):
            continue
        if decoded.isprintable():
            variants.append(normalized_text(decoded))
    return '\n'.join(variants)


def classify_input(text: str) -> str:
    normalized = inspection_text(text)
    if any(re.search(pattern, normalized, re.DOTALL | re.IGNORECASE) for pattern in INJECTION_PATTERNS):
        return 'injection'
    if any(re.search(pattern, normalized, re.DOTALL) for pattern in COMMERCIAL_PATTERNS):
        return 'commercial'
    return ''


def policy_reply(reason: str, meeting_url: str) -> str:
    """Redirige con lenguaje comercial, sin exponer controles ni instrucciones."""
    if reason == 'commercial':
        return (
            'Los valores dependen del alcance de tu entidad y los revisamos en una reunión. '
            'Si quieres ver qué plan se ajusta a tu uso, arma tu M.A.T.I.A.S. en https://www.akaike.lat/#configurador. '
            'Para la propuesta, agenda aquí: '
            f'{meeting_url}'
        )
    return (
        'Puedo ayudarte a conocer las soluciones de Akaike y M.A.T.I.A.S. para tu entidad. '
        'Cuéntame qué necesitas mejorar en tu proceso de crédito o coordinemos una conversación: '
        f'{meeting_url}'
    )


def guard_reply(text: str, meeting_url: str, system_prompt: str = '') -> str:
    """Impide publicar catálogo, importes, instrucciones internas y datos privados."""
    clean = ' '.join(re.sub(r'<[^>]+>', '', html.unescape(text or '')).replace('**', '').split())
    normalized = inspection_text(text) + '\n' + inspection_text(clean)
    blocked = (
        # Los planes vigentes (Starter, Expert, Pro, Corporate) y los AKUs son públicos; los nombres viejos no.
        r'\b(?:scale|enterprise\s+pro)\b',
        r'[$€£]\s*\d|\b(?:usd|cop|eur|pesos|dolares|euros)\b',
        r'\b(?:deepseek|openai|chatgpt|system[_ ]prompt|developer message)\b|\bgpt[- ]\d',
        r'\[/?contexto interno|<\|(?:im_start|system)\|>|\b(?:api[_ ]key|bearer)\b',
        r'postgres(?:ql)?://|\bsk-[a-z0-9_-]{12,}',
        r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b',
        r'(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)',
    )
    # Montos en dinero: las cantidades de AKUs y de uso (calificaciones, ejecuciones…) no son precios.
    montos = re.sub(r'\d[\d.,]*\s*(?:akus?|calificaciones|calificacion|ejecuciones|ejecucion|solicitudes|consultas|reportes|scores?|usuarios?)\b', ' ', normalized)
    en_dinero = (
        r'\b(?:mensualidad|precio|tarifa|cobro|cuesta|vale(?!\s+la\s+pena)|valor)\b.{0,80}\b(?:\d[\d.,]*|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|veinte|treinta|cien(?:to)?|doscientos|trescientos|cuatrocientos|quinientos|seiscientos|setecientos|ochocientos|novecientos|mil|millon(?:es)?)\b',
        r'\bsuscripcion\b.{0,40}\b(?:\d[\d.,]*|cien(?:to)?|mil|millon(?:es)?)\b',
        r'\b\d[\d.,]*\s+(?:al\s+mes|mensuales|mensual|al\s+ano|anuales|anual)\b',
    )
    if not text or any(re.search(pattern, normalized) for pattern in blocked) or any(re.search(pattern, montos) for pattern in en_dinero):
        return policy_reply('commercial', meeting_url)
    for paragraph in system_prompt.split('\n\n'):
        fragment = normalized_text(paragraph.strip())[:120]
        if len(fragment) >= 80 and fragment in normalized:
            return policy_reply('commercial', meeting_url)
    allowed_urls = {
        meeting_url.rstrip('/'), 'https://akaike.lat', 'https://www.akaike.lat',
        'https://www.akaike.lat/#configurador', 'https://www.akaike.lat/#planes',
        'https://akaike.lat/#configurador', 'https://akaike.lat/#planes',
        'https://matias-score.ai', 'https://www.matias-score.ai',
    }
    for url in re.findall(r'https?://[^\s<>()\]]+', html.unescape(text)):
        if url.rstrip('.,;:/') not in allowed_urls:
            return policy_reply('commercial', meeting_url)
    # Mantiene respuestas públicas breves y sin HTML ejecutable.
    return ' '.join(clean.split()[:150])


def safe_history(messages: list[dict], system_prompt: str, meeting_url: str) -> list[dict]:
    """Reconstruye una única política; nunca confía en roles o ataques persistidos."""
    safe = [{'role': 'system', 'content': system_prompt}]
    pregunta_pendiente = False  # el mensaje anterior es una pregunta que sí entró
    for item in messages:
        role, content = item.get('role'), item.get('content', '')
        entra = False
        if role == 'user' and not classify_input(content):
            safe.append({'role': role, 'content': content})
            entra = True
        elif role == 'assistant':
            if guard_reply(content, meeting_url, system_prompt) == content:
                safe.append({'role': role, 'content': content})
            elif pregunta_pendiente:
                # Sin su respuesta, la pregunta quedaba pendiente y el modelo la contestaba otra vez en vez
                # de la pregunta nueva (27-oct-2026): se van las dos.
                safe.pop()
        pregunta_pendiente = entra
    return safe


def public_context(text: str) -> str:
    """Quita referencias privadas antes de entregarlas al modelo comercial."""
    parts = []
    for block in re.split(r'(?m)(?=^---[^\n]+---\s*$)', text or ''):
        heading = re.match(r'^---([^\n]+)---', block)
        if heading and re.search(r'precios|tarifas|planes|cotizaciones', normalized_text(heading.group(1))):
            continue
        block = re.sub(r'(?m)^---[^\n]+---\s*$', '', block).strip()
        for paragraph in re.split(r'\n\s*\n', block):
            paragraph = paragraph.strip()
            if not paragraph or classify_input(paragraph) == 'injection':
                continue
            safe = guard_reply(paragraph, '')
            if safe != policy_reply('commercial', ''):
                parts.append(safe)
    return '\n\n'.join(parts)


class RequestSizeLimitMiddleware:
    """Acota también cuerpos chunked; Content-Length no es una prueba de tamaño."""
    def __init__(self, app, max_bytes: int = 65536, read_timeout: float = 15.0):
        self.app = app
        self.max_bytes = max_bytes
        self.read_timeout = read_timeout

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            await JSONResponse({'detail': 'Tamaño de solicitud inválido'}, status_code=400)(scope, receive, send)
            return
        if declared > self.max_bytes:
            await JSONResponse({'detail': 'Solicitud demasiado grande'}, status_code=413)(scope, receive, send)
            return
        parts, size = [], 0
        deadline = asyncio.get_running_loop().time() + self.read_timeout
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - asyncio.get_running_loop().time()))
            except TimeoutError:
                await JSONResponse({'detail': 'Tiempo de solicitud agotado'}, status_code=408)(scope, receive, send)
                return
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > self.max_bytes:
                await JSONResponse({'detail': 'Solicitud demasiado grande'}, status_code=413)(scope, receive, send)
                return
            if body:
                parts.append(body)
            if not message.get('more_body', False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': b''.join(parts), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)
