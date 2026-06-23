"""
Knowledge base para el agente de presentaciones M.A.T.I.A.S.
Búsqueda semántica mejorada con stemming español y slide awareness.
"""
import os
import re
from pathlib import Path
from typing import Optional

KB_DIR = os.environ.get(
    "KB_DIR",
    str(Path(__file__).resolve().parent / "conocimiento")
)

_docs: list[dict] = []
_loaded = False

# Palabras vacías en español
STOP_WORDS = {
    "para", "como", "que", "los", "las", "del", "una", "con", "por", "más",
    "sus", "este", "esta", "entre", "hay", "sin", "pero", "todo", "sobre",
    "cada", "muy", "era", "fue", "han", "ser", "tiene", "son", "está",
    "hace", "puede", "desde", "hasta", "donde", "cual", "cuando", "quien",
    "también", "porque", "tiene", "esto", "solo", "ellos", "ellas", "tiene",
    "están", "sido", "estar", "haber", "tener", "hacer", "decir", "había",
    "ahora", "antes", "después", "siempre", "estos", "estas", "ese", "esa",
}

# Mapeo de stemming español básico (sufijos comunes)
SUFFIXES = ["ción", "idad", "mente", "anza", "encia", "miento", "mente", 
            "ores", "ales", "ivos", "idas", "ados", "idas", "eras", "eros",
            "amos", "emos", "imos", "aron", "eron", "irán", "arán",
            "ando", "endo", "iendo", "as", "es", "is", "os", "us",
            "ar", "er", "ir"]


def _stem(word: str) -> str:
    """Stemming español básico."""
    word = word.lower()
    if len(word) <= 3:
        return word
    for suffix in sorted(SUFFIXES, key=len, reverse=True):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def _tokenize(text: str) -> set[str]:
    """Extrae stems únicos de un texto, incluyendo números y porcentajes."""
    # Palabras en español (3+ letras)
    words = re.findall(r"[a-záéíóúñ]{3,}", text.lower())
    # Números significativos (incluyendo porcentajes, ratios como 5:1, años)
    numbers = re.findall(r"\d+%|\d+:\d+|\b20\d{2}\b|\d+[.,]?\d*\s*(millones|mil|billones|%|por ciento)", text.lower())
    
    stems = set()
    for w in words:
        if w not in STOP_WORDS:
            s = _stem(w)
            if len(s) >= 2:
                stems.add(s)
    
    for n in numbers:
        normalized = n.strip().replace(" ", "").replace(",", ".")
        stems.add(normalized)
    
    return stems


def load_knowledge_base():
    """Carga todos los archivos .md en memoria."""
    global _docs, _loaded
    if _loaded:
        return

    kb_path = Path(KB_DIR)
    if not kb_path.exists():
        _loaded = True
        return

    for md_file in sorted(kb_path.glob("*.md")):
        try:
            with open(md_file, "r") as f:
                content = f.read()
            name = md_file.stem
            
            # Extraer secciones (separadas por ---)
            sections = []
            current_section = []
            for line in content.split("\n"):
                if line.strip() == "---" and current_section:
                    sections.append("\n".join(current_section))
                    current_section = []
                else:
                    current_section.append(line)
            if current_section:
                sections.append("\n".join(current_section))
            
            # Indexar tokens del documento completo
            tokens = _tokenize(content)
            
            _docs.append({
                "name": name,
                "path": str(md_file),
                "content": content,
                "sections": sections,
                "tokens": tokens,
                "length": len(content),
            })
        except Exception:
            pass

    _loaded = True


def search_relevant(question: str, slide_index: int = -1, max_chars: int = 12000) -> str:
    """
    Búsqueda mejorada: TF-IDF-like con stemming español.
    
    Args:
        question: la pregunta del usuario
        slide_index: índice de la diapositiva actual (0-based, -1 si desconocido)
        max_chars: máximo de caracteres a devolver
    """
    load_knowledge_base()

    if not _docs:
        return ""

    # Tokenizar pregunta
    q_tokens = _tokenize(question)
    
    if not q_tokens:
        return ""

    # Puntuar documentos
    scored = []
    for doc in _docs:
        # Score: intersección de tokens ponderada por IDF-like factor
        common = q_tokens & doc["tokens"]
        if not common:
            continue
        
        # TF-IDF-like: tokens coincidentes / log(longitud doc)
        tf = len(common) / len(q_tokens)  # qué fracción de la pregunta cubre
        idf_like = len(common) / max(1, len(doc["tokens"]))  # qué tan específicos son
        
        # Bonus por título
        title_tokens = _tokenize(doc["name"])
        title_bonus = len(q_tokens & title_tokens) * 2
        
        score = (tf * 15) + (idf_like * 10) + title_bonus
        
        # Slide awareness: si sabemos la diapositiva, dar bonus a docs con números similares
        if slide_index >= 0:
            doc_num = _extract_doc_number(doc["name"])
            if doc_num is not None and abs(doc_num - (slide_index + 1)) <= 2:
                score += 10
        
        scored.append((score, doc))

    # Ordenar por score, tomar top 10
    scored.sort(key=lambda x: x[0], reverse=True)

    context_parts = []
    total_chars = 0
    for score, doc in scored[:10]:
        # Buscar sección más relevante en vez del inicio del doc
        excerpt = _find_best_section(doc, question, q_tokens)
        context_parts.append(f"--- Fuente: {doc['name']} ---\n{excerpt}")
        total_chars += len(excerpt)
        if total_chars > max_chars:
            break

    return "\n\n".join(context_parts)


def _find_best_section(doc: dict, question: str, q_tokens: set) -> str:
    """Encuentra la sección más relevante dentro del documento."""
    if not doc["sections"]:
        return doc["content"][:3000]
    
    best_score = 0
    best_section = doc["content"][:3000]
    
    for sec in doc["sections"]:
        if len(sec) < 20:
            continue
        sec_tokens = _tokenize(sec)
        common = q_tokens & sec_tokens
        if len(common) >= best_score:
            best_score = len(common)
            best_section = sec
    
    # Tomar sección + contexto alrededor
    return best_section[:4000]


def _extract_doc_number(name: str) -> Optional[int]:
    """Extrae el número de un documento AkaikeN."""
    m = re.match(r"akaike(\d+)", name.lower())
    if m:
        return int(m.group(1))
    return None


def get_kb_stats() -> dict:
    """Estadísticas de la base de conocimiento."""
    load_knowledge_base()
    return {
        "total_docs": len(_docs),
        "total_chars": sum(d["length"] for d in _docs),
        "docs": [d["name"] for d in _docs],
    }
