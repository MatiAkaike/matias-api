"""Runtime liviano del grafo público y del perfil lingüístico de Oscar."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "oscar_graph"
CORPUS_PATH = BASE_DIR / "public_corpus.jsonl"
STYLE_PATH = BASE_DIR / "style_profile.json"
GRAPH_PATH = BASE_DIR / "knowledge_graph.json"

STOP_WORDS = {
    "para", "como", "que", "los", "las", "del", "una", "con", "por", "mas", "sus",
    "este", "esta", "entre", "hay", "sin", "pero", "todo", "sobre", "cada", "ser",
    "son", "esta", "puede", "desde", "hasta", "donde", "cual", "cuando", "tambien",
}

_documents: list[dict] | None = None
_document_frequency: Counter = Counter()
_style: dict | None = None
_graph_nodes: dict[str, dict] = {}
_graph_edges: list[dict] = []
_average_length = 1.0

DOMAIN_TERMS = {
    "akaike", "matias", "copilot", "credito", "credit", "riesgo", "scoring", "score",
    "scorecard", "modelo", "modelos", "cartera", "morosidad", "default", "incumplimiento",
    "perdida", "pd", "lgd", "ead", "gini", "auc", "ks", "psi", "logit", "buro", "buro",
    "cobranza", "originacion", "provision", "capital", "validacion", "calibracion", "monitoreo",
    "ustedes", "empresa", "servicio", "servicios", "producto", "solucion", "entrenamiento",
    "planes", "implementacion", "datos", "variables", "rentabilidad", "aprobacion",
}
SLIDE_FOLLOWUP_TERMS = {
    "esto", "eso", "esta", "diapositiva", "significa", "explica", "explicame", "ejemplo",
    "detalle", "anterior", "muestra", "dice", "funciona", "beneficio", "beneficios", "ventaja",
}


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"m\s*\.\s*a\s*\.\s*t\s*\.\s*i\s*\.\s*a\s*\.\s*s\s*\.?", "matias", text.lower())
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return [
        token for token in re.findall(r"[a-zñ0-9%]{2,}", normalized)
        if token not in STOP_WORDS and not token.isdigit()
    ]


def is_domain_question(text: str) -> bool:
    return bool(set(_tokens(text)) & DOMAIN_TERMS)


def is_slide_followup(text: str) -> bool:
    return bool(set(_tokens(text)) & SLIDE_FOLLOWUP_TERMS)


def _load() -> None:
    global _documents, _style, _document_frequency, _average_length, _graph_nodes, _graph_edges
    if _documents is not None:
        return
    _documents = []
    _document_frequency = Counter()
    if CORPUS_PATH.exists():
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            tokens = _tokens(item.get("text", ""))
            if not tokens:
                continue
            item["tokens"] = tokens
            item["tf"] = Counter(tokens)
            _documents.append(item)
            for token in set(tokens):
                _document_frequency[token] += 1
    if _documents:
        _average_length = sum(len(item["tokens"]) for item in _documents) / len(_documents)
    _style = json.loads(STYLE_PATH.read_text(encoding="utf-8")) if STYLE_PATH.exists() else {}
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8")) if GRAPH_PATH.exists() else {}
    _graph_nodes = {node["id"]: node for node in graph.get("nodes", [])}
    _graph_edges = graph.get("edges", [])


def _graph_context(query: list[str], limit: int = 8) -> list[str]:
    """Expande conceptos conectados para que el grafo sí participe en la respuesta."""
    query_set = set(query)
    ranked = sorted(
        (
            (len(query_set & set(_tokens(node.get("label", "")))), node_id)
            for node_id, node in _graph_nodes.items()
        ),
        reverse=True,
    )
    seeds = {node_id for overlap, node_id in ranked[:6] if overlap > 0}
    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in _graph_edges:
        source_id = str(edge.get("source", ""))
        target_id = str(edge.get("target", ""))
        if source_id not in seeds and target_id not in seeds:
            continue
        source = _graph_nodes.get(source_id, {}).get("label", "")
        target = _graph_nodes.get(target_id, {}).get("label", "")
        relation = edge.get("relation", "RELACIONADO_CON")
        item = (source, relation, target)
        if not source or not target or item in seen:
            continue
        seen.add(item)
        lines.append(f"{source} — {relation} — {target}")
        if len(lines) >= limit:
            break
    return lines


def search(question: str, max_chars: int = 9000) -> tuple[str, list[str]]:
    """Recupera hechos públicos con procedencia; nunca consulta voz privada."""
    _load()
    if not _documents:
        return "", []
    query = list(dict.fromkeys(_tokens(question)))
    if not query or not (set(query) & DOMAIN_TERMS):
        return "", []
    known_query = {token for token in query if token in _document_frequency}
    unknown_query = {token for token in query if token not in _document_frequency and len(token) >= 5}
    if not known_query or (unknown_query and len(known_query) < 2):
        return "", []
    total = len(_documents)
    risk_terms = {"score", "scorecard", "credit", "credito", "riesgo", "modelo", "validacion", "validar", "pd", "lgd", "ead", "gini", "ks", "psi", "perdida", "default", "logit"}
    product_terms = {"matias", "precio", "cuesta", "plan", "api", "implementacion", "copilot"}
    query_set = set(query)
    scored: list[tuple[float, dict]] = []
    for document in _documents:
        score = 0.0
        for token in query:
            frequency = document["tf"].get(token, 0)
            if not frequency:
                continue
            df = _document_frequency.get(token, 1)
            idf = math.log((total - df + 0.5) / (df + 0.5) + 1)
            length_norm = 1.5 * (0.25 + 0.75 * len(document["tokens"]) / _average_length)
            score += idf * (frequency * 2.5) / (frequency + length_norm)
        if query_set & risk_terms and document.get("access") == "public_theory":
            score *= 1.6
        if query_set & product_terms and document.get("access") == "public_product":
            score *= 1.5
        if score > 0:
            scored.append((score, document))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    graph_lines = _graph_context(query)
    context: list[str] = []
    sources: list[str] = []
    used = 0
    if graph_lines:
        graph_text = "--- RELACIONES DEL GRAFO ---\n" + "\n".join(graph_lines)
        context.append(graph_text)
        sources.append("Grafo de conocimiento Akaike")
        used = len(graph_text)
    source_uses: Counter = Counter()
    for _, document in scored[:30]:
        text = document["text"]
        raw_source = document["source_id"]
        source = "Credit Risk Papers" if document.get("access") == "public_theory" else document["source"]
        if source_uses[raw_source] >= 2:
            continue
        if context and used + len(text) > max_chars:
            continue
        if source not in sources:
            sources.append(source)
        source_uses[raw_source] += 1
        source_type = "TEORÍA" if document.get("access") == "public_theory" else "PRODUCTO AKAIKE"
        context.append(f"--- FUENTE {source_type}: {source} ---\n{text}")
        used += len(text)
        if used >= max_chars:
            break
    return "\n\n".join(context), sources


def style_prompt() -> str:
    """Traduce estadísticas agregadas a instrucciones de forma, no de hechos."""
    _load()
    if not _style:
        return ""
    statistics = _style.get("statistics", {})
    markers = [item["text"] for item in _style.get("discourse_markers", [])[:10]]
    trigrams = [item["text"] for item in _style.get("top_trigrams", [])[:15]]
    constructions = f"Construcciones frecuentes: {', '.join(trigrams)}.\n" if trigrams else ""
    return (
        "CAPA DE VOZ CALIBRADA CON TRANSCRIPCIONES REALES DE OSCAR:\n"
        f"Corpus analizado: {statistics.get('oscar_words', 0)} palabras en "
        f"{statistics.get('oscar_utterances', 0)} intervenciones. "
        f"Longitud oral media: {statistics.get('average_utterance_words', 0)} palabras.\n"
        f"Marcadores frecuentes: {', '.join(markers)}.\n"
        f"{constructions}"
        "Replica el ritmo: idea central, explicación causal y ejemplo aplicado. "
        "Usa los marcadores con naturalidad, nunca todos juntos ni como caricatura. "
        "Esta capa define únicamente la forma de explicar. No aporta hechos, cifras ni nombres. "
        "No afirmes ser Oscar ni cites reuniones privadas. Si preguntan, eres el asistente de Akaike calibrado con su estilo."
    )


def stats() -> dict:
    _load()
    return {
        "public_graph_chunks": len(_documents or []),
        "style_statistics": (_style or {}).get("statistics", {}),
    }
