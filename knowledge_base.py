"""
Knowledge base para el agente de presentaciones M.A.T.I.A.S.
Carga y busca en los archivos .md de /Volumes/OpenClaw/Conocimiento Presentaciones/
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
            _docs.append({
                "name": name,
                "path": str(md_file),
                "content": content,
                "length": len(content),
            })
        except Exception:
            pass

    _loaded = True


def search_relevant(question: str, max_chars: int = 8000) -> str:
    """
    Busca los documentos más relevantes para la pregunta.
    Usa matching simple por keywords.
    """
    load_knowledge_base()

    if not _docs:
        return ""

    # Extraer keywords de la pregunta (palabras de 4+ caracteres)
    keywords = set(re.findall(r"[a-záéíóúñ]{4,}", question.lower()))

    scored = []
    for doc in _docs:
        content_lower = doc["content"].lower()
        title_lower = doc["name"].lower()

        # Score: coincidencias en título valen más
        score = sum(5 for k in keywords if k in title_lower)
        # Coincidencias en contenido
        score += sum(1 for k in keywords if k in content_lower)

        if score > 0:
            scored.append((score, doc))

    # Ordenar por score descendente, tomar top 5
    scored.sort(key=lambda x: x[0], reverse=True)

    context_parts = []
    total_chars = 0
    for score, doc in scored[:5]:
        excerpt = doc["content"][:3000]
        context_parts.append(f"--- {doc['name']} ---\n{excerpt}")
        total_chars += len(excerpt)
        if total_chars > max_chars:
            break

    return "\n\n".join(context_parts)


def get_kb_stats() -> dict:
    """Estadísticas de la base de conocimiento."""
    load_knowledge_base()
    return {
        "total_docs": len(_docs),
        "total_chars": sum(d["length"] for d in _docs),
        "docs": [d["name"] for d in _docs],
    }
