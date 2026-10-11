"""Portafolio público vigente: productos, no planes ni precios."""
import re
from pathlib import Path

from chat_security import normalized_text

CONTEXT = (Path(__file__).resolve().parent / 'conocimiento' / 'MATIAS_OS_PORTAFOLIO_PUBLICO.md').read_text(encoding='utf-8')


def is_overview_question(question: str) -> bool:
    text = normalized_text(question).replace('m.a.t.i.a.s.', 'matias').replace('m.a.t.i.a.s', 'matias')
    brand = r'(?:akaike|matias(?:\s+os)?)'
    # Solo solicitudes inequívocas del catálogo general, no menciones sueltas.
    patterns = (
        rf'\W*(?:que|cuales)(?:\s+son)?\s+(?:(?:los|sus|tus)\s+)?(?:productos|servicios|soluciones)(?:\s+de\s+{brand})?(?:\s+(?:ofrecen|tienen|ofrece\s+{brand}|tiene\s+{brand}))?\W*',
        rf'\W*(?:(?:cual(?:es)?(?:\s+(?:es|son))?|muestrame|dime|quiero\s+(?:ver|conocer))\s+)?(?:el\s+)?portafolio(?:\s+completo)?(?:\s+de\s+(?:servicios|productos|soluciones))?(?:\s+de\s+{brand})?\W*',
    )
    return any(re.fullmatch(pattern, text) for pattern in patterns)


def is_relevant(question: str) -> bool:
    text = normalized_text(question)
    return is_overview_question(question) or bool(re.search(
        r'\b(?:matias|akaike|credit|copilot|signals|flows|brain|scoring|credito|training|erp|mcp|terminal|omnicanal|desembolso|data\s+b[. ]?i)\b', text
    ))


def overview_reply(meeting_url: str) -> str:
    return (
        'M.A.T.I.A.S. OS reúne seis productos: Credit Score, predicción de riesgo personalizada; '
        'Copilot, asistencia al analista; Signals, señales del recorrido digital; '
        'Flows, procesos y políticas de crédito; Data B.I., inteligencia de negocios; '
        'y Credit Agent, misiones operativas con atribuciones y supervisión. '
        'Training Center / Matías Brain aporta el conocimiento institucional. '
        'Para revisar la disponibilidad y el alcance para tu entidad, agenda una reunión: '
        f'{meeting_url}'
    )
