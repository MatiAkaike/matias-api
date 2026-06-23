"""
Knowledge base con chunking + BM25 para RAG de presentaciones.
Cada documento se divide en chunks de ~1500 caracteres con overlap.
"""
import os, re, math
from pathlib import Path
from typing import Optional
from collections import Counter

KB_DIR = os.environ.get("KB_DIR", str(Path(__file__).resolve().parent / "conocimiento"))

STOP_WORDS = {
    "para", "como", "que", "los", "las", "del", "una", "con", "por", "más",
    "sus", "este", "esta", "entre", "hay", "sin", "pero", "todo", "sobre",
    "cada", "muy", "era", "fue", "han", "ser", "tiene", "son", "está",
    "hace", "puede", "desde", "hasta", "donde", "cual", "cuando", "quien",
    "también", "porque", "esto", "solo", "ellos", "ellas", "están",
    "sido", "estar", "haber", "tener", "hacer", "decir", "había",
    "ahora", "antes", "después", "siempre", "estos", "estas", "ese", "esa",
    "entonces", "digamos", "bueno", "pues", "listo", "claro",
    "ok", "okay", "sí", "no", "muchas", "gracias", "mil",
    "voy", "va", "van", "digo", "dice", "dicen", "ahí", "allí",
    "al", "años", "dos", "tres", "vez", "parte", "lado",
    "cosas", "cosa", "tema", "día", "manera", "forma",
}

_chunks: list[dict] = []
_loaded = False
_df = Counter()
_total_chunks = 0

CHUNK_SIZE = 1500
OVERLAP = 300


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-záéíóúñ0-9%]{2,}", text.lower())
    return [w for w in words if w not in STOP_WORDS and not w.isdigit()]


def _ngrams(tokens: list[str], n: int = 2) -> list[str]:
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def _chunk_text(text: str) -> list[str]:
    """Divide texto en chunks con overlap."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        chunks.append(chunk)
        i += CHUNK_SIZE - OVERLAP
    return chunks


def load_knowledge_base():
    global _chunks, _loaded, _df, _total_chunks
    if _loaded:
        return

    kb_path = Path(KB_DIR)
    if not kb_path.exists():
        _loaded = True
        return

    raw_chunks = []
    for md_file in sorted(kb_path.glob("*.md")):
        try:
            with open(md_file, "r") as f:
                content = f.read()
            
            name_lower = md_file.stem.lower()
            
            # Detectar si es transcripción: mirar los primeros 1000 caracteres del documento
            is_transcript_doc = bool(re.search(r"@\d+:\d+", content[:1000]))
            is_technical_doc = any(kw in name_lower for kw in 
                ["entrena", "implementación", "implementacion", "requerimientos",
                 "precios", "seguridad", "stack", "documentación", "documentacion",
                 "copilot", "api", "arquitectura", "matias api", "matias_api"])
            
            # Saltar transcripciones de reuniones (Akaike1-26) que no sean docs técnicos
            if is_transcript_doc and not is_technical_doc and re.match(r"akaike\d+", name_lower):
                continue
            
            for ci, chunk_text in enumerate(_chunk_text(content)):
                if len(chunk_text) < 50:
                    continue
                tokens = _tokenize(chunk_text)
                if not tokens:
                    continue
                bigrams = _ngrams(tokens, 2)
                tf = Counter(tokens)
                bf = Counter(bigrams)
                
                raw_chunks.append({
                    "source": md_file.stem,
                    "chunk_idx": ci,
                    "text": chunk_text,
                    "tokens": tokens,
                    "bigrams": bigrams,
                    "tf": tf,
                    "bf": bf,
                    "length": len(tokens),
                })
        except Exception:
            pass

    _total_chunks = len(raw_chunks)
    if _total_chunks == 0:
        _loaded = True
        return

    for ch in raw_chunks:
        for token in ch["tf"]:
            _df[token] += 1
        for bg in ch["bf"]:
            _df[bg] += 1

    _chunks = raw_chunks
    _loaded = True


def _bm25_chunk(query_tokens, query_bigrams, chunk):
    k1, b = 1.5, 0.75
    score = 0.0
    for token in query_tokens:
        if token not in chunk["tf"]:
            continue
        tf = chunk["tf"][token]
        df = _df.get(token, 1)
        idf = math.log((_total_chunks - df + 0.5) / (df + 0.5) + 1)
        norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * chunk["length"] / 100))  # avg ~100 tokens
        score += idf * norm
    for bg in query_bigrams:
        if bg not in chunk["bf"]:
            continue
        tf = chunk["bf"][bg]
        df = _df.get(bg, 1)
        idf = math.log((_total_chunks - df + 0.5) / (df + 0.5) + 1)
        norm = (tf * (k1 + 1)) / (tf + k1)
        score += idf * norm * 4.0  # bigrams pesan 4x
    return score


def search_relevant(question: str, slide_index: int = -1, max_chars: int = 12000) -> str:
    load_knowledge_base()
    if not _chunks:
        return ""

    q_tokens = _tokenize(question)
    q_bigrams = _ngrams(q_tokens, 2)
    if not q_tokens:
        return ""

    # Score cada chunk
    scored = []
    for ch in _chunks:
        s = _bm25_chunk(q_tokens, q_bigrams, ch)
        if s <= 0:
            continue
        
        # BOOST: documentos estructurados vs transcripciones
        source_lower = ch["source"].lower()
        text_lower = ch["text"].lower()
        
        boost = 1.0
        # Boost por título de documento
        if any(kw in source_lower for kw in ["entrena", "implementación", "implementacion", "requerimientos", "precios", "seguridad", "stack", "documentación", "documentacion"]):
            boost *= 3.0
        elif any(kw in source_lower for kw in ["copilot", "api", "arquitectura"]):
            boost *= 2.0
        
        # Boost por CONTENIDO que indica documento técnico/estructurado (no conversación)
        tech_markers = ["análisis forense", "analisis forense", "curación de datos", "curacion de datos",
                       "ingeniería de variables", "ingenieria de variables", "entrenamiento del modelo",
                       "metodología", "metodologia", "5:1", "roi", "credit scoring",
                       "gini", "ks", "psi", "modelo estadístico", "modelo estadistico"]
        tech_hits = sum(1 for m in tech_markers if m in text_lower)
        if tech_hits >= 3:
            boost *= 4.0
        elif tech_hits >= 1:
            boost *= 2.0
        
        # Penalización por contenido de conversación (transcripciones con timecodes)
        if "@" in ch["text"][:200] and ":" in ch["text"][:200]:
            boost *= 0.3  # Penalizar transcripciones
        
        s *= boost
        
        if s > 0.01:
            scored.append((s, ch))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Tomar top 10 chunks, agrupar por fuente
    seen_sources = set()
    context_parts = []
    total = 0
    for score, ch in scored[:15]:
        source_key = f"{ch['source']}_{ch['chunk_idx']}"
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        
        context_parts.append(f"--- {ch['source']} (chunk {ch['chunk_idx']}) ---\n{ch['text']}")
        total += len(ch['text'])
        if total > max_chars:
            break

    return "\n\n".join(context_parts)


def get_kb_stats() -> dict:
    load_knowledge_base()
    return {"total_chunks": len(_chunks), "total_sources": len(set(c["source"] for c in _chunks))}
