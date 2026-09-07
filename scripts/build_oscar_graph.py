#!/usr/bin/env python3
"""Construye el grafo privado y exporta artefactos públicos sin PII."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

try:
    import fitz
except ImportError:
    fitz = None

ROOT = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Akaike CRS"
RISK = ROOT / "Credit Risk Papers"
RAW = Path.home() / ".local" / "share" / "matias-oscar-graph" / "raw"
OUT = Path.home() / ".local" / "share" / "matias-oscar-graph"
DB_PATH = OUT / "oscar_knowledge_graph.sqlite"
EXPORT = Path(__file__).resolve().parents[1] / "oscar_graph"
FATHOM_PATH = RAW / "fathom_meetings.json"

TEXT_EXTS = {".md", ".txt", ".csv", ".json", ".html", ".xml"}
OFFICE_EXTS = {".docx", ".pptx"}
SUPPORTED_EXTS = TEXT_EXTS | OFFICE_EXTS | {".pdf"}
SENSITIVE_PARTS = {
    "dian", "bancos", "gastos", "colaboradores", "rut", "recibos de impuestos",
    "cuentas de cobro", "contrato", "nda", "certificación", "certificacion",
}
PUBLIC_MATIAS_TITLES = {
    "m.a.t.i.a.s. y m.a.t.i.a.s. copilot",
    "akaike credit risk solutions – teaser ejecutivo",
    "implementación de m.a.t.i.a.s. sin data histórica propia",
    "precios oficiales m.a.t.i.a.s. 2026",
    "planes m.a.t.i.a.s.",
    "akaike presentación de servicios 2026 - m.a.t.i.a.s.",
    "akaike presentación de servicios 2026 - m.a.t.i.a.s.sp",
    "presentación de servicios 2025 - m.a.t.i.a.s. sp",
    "cómo se entrena m.a.t.i.a.s.",
    "versión clientes - seguridad, privacidad y uso responsable de la información m.a.t.i.a.s. copilot",
    "versión clientes - seguridad, privacidad y uso responsable de la información m.a.t.i.a.s. copilot 2",
}
WORD_RE = re.compile(r"[a-záéíóúüñ]+(?:'[a-záéíóúüñ]+)?", re.I)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
PII_PATTERNS = [
    (re.compile(r"(?i)\bcitation_key\s*:\s*\S+"), "reference_id: [omitido]"),
    (re.compile(r"(?i)https?://[^\s<>\"']+"), "[enlace omitido]"),
    (re.compile(r"(?i)(?:localhost|127\.0\.0\.1)(?::\d{2,5})?"), "[host omitido]"),
    (re.compile(r"/Users/[^\s]+"), "[ruta omitida]"),
    (re.compile(r"(?i)\b(?:x-api-key|api[-_ ]?key|authorization)\s*[:=]\s*[\"']?[A-Za-z0-9._-]{4,}[\"']?"), "[credencial omitida]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[secreto omitido]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[secreto omitido]"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[correo]"),
    (re.compile(r"\b\d{7,}\b"), "[identificador]"),
]
PHONE_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
DISCOURSE = [
    "digamos", "entonces", "básicamente", "basicamente", "realmente", "finalmente",
    "es decir", "por ejemplo", "en ese sentido", "lo que pasa es que", "de alguna manera",
    "el punto es", "la idea es", "yo creo", "para mí", "para mi", "lo importante es",
    "mira", "listo", "bueno", "perfecto", "correcto", "exactamente",
]
VERB_ENDINGS = (
    "o", "as", "a", "amos", "an", "é", "aste", "ó", "aron", "ía", "ías", "íamos", "ían",
    "aré", "arás", "ará", "aremos", "arán", "ería", "erías", "eríamos", "erían",
    "iendo", "ando", "ado", "ido", "emos", "imos", "es", "en",
)
PRIVATE_NAMES: set[str] = set()
THIRD_PARTY_NAMES = {
    "Amazon Web Services", "AWS", "MassChallenge", "StartupAndes", "Colombia Fintech",
    "DataCrédito", "Datacredito", "Experian", "TransUnion", "Claro", "Upstart",
}
PRODUCT_CONCEPT_TERMS = {
    "M.A.T.I.A.S.": ("m.a.t.i.a.s", "matias"),
    "Credit Scoring": ("credit scoring", "scorecard"),
    "API de decisión": ("api", "web service"),
    "Originación": ("originación", "originacion"),
    "Comportamiento": ("comportamiento", "behaviour"),
    "Cobranza": ("cobranza", "collection scoring"),
    "Copilot": ("copilot",),
    "Seguridad": ("seguridad", "privacidad"),
    "Implementación": ("implementación", "implementacion"),
    "Monitoreo": ("monitoreo", "seguimiento"),
    "Planes": ("starter", "enterprise", "planes"),
    "Datos y variables": ("variables", "datos históricos", "data histórica"),
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:180]


def redact(text: str) -> str:
    clean = text
    clean = PHONE_CANDIDATE_RE.sub(
        lambda match: "[teléfono]" if len(re.findall(r"\d", match.group(0))) >= 9 else match.group(0),
        clean,
    )
    for pattern, replacement in PII_PATTERNS:
        clean = pattern.sub(replacement, clean)
    for name in sorted(PRIVATE_NAMES, key=len, reverse=True):
        clean = re.sub(
            r"(?<![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9])" + re.escape(name) + r"(?![A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9])",
            "[entidad]" if name in THIRD_PARTY_NAMES else "[persona]",
            clean,
            flags=re.IGNORECASE,
        )
    clean = re.sub(
        r"\b(cliente|cooperativa|financiera|banco|empresa|fundación|fundacion|fondo)\s+"
        r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ&.-]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ&.-]{2,}){0,3}",
        r"\1 [entidad]",
        clean,
    )
    return clean


def collect_public_author_names() -> None:
    """Identifica autores del wiki para que nunca lleguen al artefacto público."""
    for path in RISK.glob("wiki/**/*.md"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for value in re.findall(r"(?im)^\s*authors?\s*:\s*(.+)$", raw):
            for name in re.split(r"\s*;\s*|\s+and\s+|\s+y\s+", value.strip()):
                normalized = normalize(name.strip("[]'\""))
                if len(normalized.split()) >= 2:
                    PRIVATE_NAMES.add(normalized)
                    for token in normalized.split():
                        if len(token) >= 5:
                            PRIVATE_NAMES.add(token)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def xml_text_from_zip(path: Path, prefixes: tuple[str, ...]) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.startswith(prefixes) or not name.endswith(".xml"):
                continue
            try:
                root = ElementTree.fromstring(archive.read(name))
                text = " ".join(node.text or "" for node in root.iter() if node.text)
                if text.strip():
                    parts.append(text)
            except Exception:
                continue
    return "\n".join(parts)


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTS:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            if ext == ".html":
                raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
                raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
                raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
            return normalize(raw)
        if ext == ".docx":
            return normalize(xml_text_from_zip(path, ("word/",)))
        if ext == ".pptx":
            return normalize(xml_text_from_zip(path, ("ppt/slides/", "ppt/notesSlides/")))
        if ext == ".pdf" and fitz:
            document = fitz.open(path)
            try:
                return normalize("\n".join(page.get_text("text") for page in document))
            finally:
                document.close()
    except Exception:
        return ""
    return ""


def access_level(path: Path) -> str:
    lower = str(path.relative_to(ROOT)).lower()
    name = path.stem.lower()
    if any(part in lower for part in SENSITIVE_PARTS):
        return "restricted"
    if str(path).startswith(str(RISK)):
        return "public_theory"
    if lower.replace("\\", "/").startswith("matias/") and any(slug(name) == slug(term) for term in PUBLIC_MATIAS_TITLES):
        return "public_product"
    return "internal"


def doc_kind(path: Path) -> str:
    lower = path.name.lower()
    if any(term in lower for term in ("transcrip", "transcript")):
        return "transcript"
    if any(term in lower for term in ("acta", "reunión", "reunion")):
        return "minutes"
    if str(path).startswith(str(RISK)):
        return "credit_risk"
    return "document"


def can_export_public_text(path: Path, level: str) -> bool:
    """Exporta teoría sintetizada y documentos propios, nunca libros/PDF crudos."""
    if level == "public_product":
        lower = path.name.lower()
        blocked = ("demo", "ejemplo", "workflow", "hdc+", "manual de implementacion ws")
        return path.suffix.lower() in {".md", ".docx", ".pdf", ".pptx"} and not any(term in lower for term in blocked)
    if level != "public_theory":
        return False
    relative = str(path.relative_to(RISK)).replace("\\", "/").lower()
    curated_prefixes = ("wiki/concepts/", "wiki/sources/", "wiki/analyses/")
    return relative == "index.md" or (relative.startswith(curated_prefixes) and path.stat().st_size <= 50_000)


def chunks(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    words = text.split()
    result = []
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        part = " ".join(words[start:start + size])
        if len(part) >= 120:
            result.append(part)
        if start + size >= len(words):
            break
    return result


def is_oscar(speaker: object) -> bool:
    if not isinstance(speaker, dict):
        return False
    display = slug(normalize(str(speaker.get("display_name", ""))))
    email = normalize(str(speaker.get("matched_calendar_invitee_email", ""))).lower()
    return email == "oscar@akaike.co" or display in {"oscar-gutierrez", "oscar-g-gutierrez-m"}


def safe_voice_example(text: str) -> str | None:
    clean = redact(normalize(text))
    if len(clean) < 80 or len(clean) > 900:
        return None
    if "[correo]" in clean or "[teléfono]" in clean or "[identificador]" in clean:
        return None
    return clean


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, path TEXT, title TEXT, source_type TEXT, access_level TEXT,
            sha256 TEXT, chars INTEGER, words INTEGER, extracted INTEGER, metadata_json TEXT
        );
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, source_id TEXT, chunk_index INTEGER, access_level TEXT,
            text TEXT, FOREIGN KEY(source_id) REFERENCES sources(id)
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(text, source_id UNINDEXED, access_level UNINDEXED);
        CREATE TABLE meetings (
            id TEXT PRIMARY KEY, title TEXT, created_at TEXT, utterances INTEGER, oscar_utterances INTEGER,
            metadata_json TEXT
        );
        CREATE TABLE utterances (
            id TEXT PRIMARY KEY, meeting_id TEXT, speaker_role TEXT, timestamp TEXT, text TEXT,
            FOREIGN KEY(meeting_id) REFERENCES meetings(id)
        );
        CREATE VIRTUAL TABLE utterances_fts USING fts5(text, meeting_id UNINDEXED, speaker_role UNINDEXED);
        CREATE TABLE meeting_artifacts (
            id TEXT PRIMARY KEY, meeting_id TEXT, artifact_type TEXT, text TEXT,
            FOREIGN KEY(meeting_id) REFERENCES meetings(id)
        );
        CREATE VIRTUAL TABLE meeting_artifacts_fts USING fts5(text, meeting_id UNINDEXED, artifact_type UNINDEXED);
        CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, label TEXT, access_level TEXT, metadata_json TEXT);
        CREATE TABLE edges (
            source_id TEXT, relation TEXT, target_id TEXT, weight REAL, evidence_source TEXT,
            PRIMARY KEY(source_id, relation, target_id, evidence_source)
        );
        CREATE TABLE style_features (feature_type TEXT, feature TEXT, count INTEGER, rate REAL,
            PRIMARY KEY(feature_type, feature));
        """
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    EXPORT.mkdir(parents=True, exist_ok=True)
    if not FATHOM_PATH.exists():
        raise RuntimeError("Falta el snapshot completo de Fathom")
    meetings = json.loads(FATHOM_PATH.read_text(encoding="utf-8"))
    db_build_path = DB_PATH.with_suffix(".sqlite.tmp")
    db_build_path.unlink(missing_ok=True)
    connection = sqlite3.connect(db_build_path)
    init_db(connection)
    PRIVATE_NAMES.clear()
    PRIVATE_NAMES.update(THIRD_PARTY_NAMES)
    collect_public_author_names()
    for category in ("Comercial", "Clientes", "Alianzas"):
        category_path = ROOT / category
        if category_path.exists():
            for child in category_path.iterdir():
                if child.is_dir() and len(child.name) >= 3:
                    PRIVATE_NAMES.add(normalize(child.name))
    for meeting in meetings:
        for invitee in meeting.get("calendar_invitees") or []:
            if not isinstance(invitee, dict):
                continue
            for key in ("name", "matched_speaker_display_name"):
                invitee_name = normalize(str(invitee.get(key, "")))
                if len(invitee_name.split()) >= 2 and not is_oscar({"display_name": invitee_name}):
                    PRIVATE_NAMES.add(invitee_name)
        recorder = meeting.get("recorded_by") or {}
        if isinstance(recorder, dict):
            recorder_name = normalize(str(recorder.get("name", "")))
            if len(recorder_name.split()) >= 2 and not is_oscar({"display_name": recorder_name}):
                PRIVATE_NAMES.add(recorder_name)
        for item in meeting.get("transcript") or []:
            if not isinstance(item, dict) or is_oscar(item.get("speaker")):
                continue
            speaker = item.get("speaker") or {}
            display_name = normalize(str(speaker.get("display_name", ""))) if isinstance(speaker, dict) else ""
            if len(display_name.split()) >= 2:
                PRIVATE_NAMES.add(display_name)

    manifest: list[dict] = []
    public_chunks: list[dict] = []
    public_chunk_hashes: set[str] = set()
    concept_edges: Counter[tuple[str, str, str, str]] = Counter()
    extracted_docs = 0
    extracted_words = 0

    for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and not p.name.startswith(".~")):
        try:
            relative = str(path.relative_to(ROOT))
            source_id = "doc:" + hashlib.sha256(relative.encode()).hexdigest()[:20]
            level = access_level(path)
            kind = doc_kind(path)
            supported = path.suffix.lower() in SUPPORTED_EXTS
            # Documentos altamente sensibles se representan, pero su contenido no se copia al grafo.
            text = "" if level == "restricted" else (extract_text(path) if supported else "")
            sha = file_hash(path)
            word_count = len(WORD_RE.findall(text.lower()))
            extracted = bool(text)
            if extracted:
                extracted_docs += 1
                extracted_words += word_count
            metadata = {"relative_path": relative, "extension": path.suffix.lower(), "size": path.stat().st_size}
            connection.execute(
                "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, relative, path.stem, kind, level, sha, len(text), word_count, int(extracted), json.dumps(metadata, ensure_ascii=False)),
            )
            connection.execute(
                "INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)",
                (source_id, "source", path.stem, level, json.dumps({"source_type": kind}, ensure_ascii=False)),
            )
            manifest.append({"id": source_id, "path": relative, "kind": kind, "access": level, "sha256": sha, "extracted": extracted, "words": word_count})
            if level == "public_product" and can_export_public_text(path, level):
                lower_text = text.lower()
                for concept_label, terms in PRODUCT_CONCEPT_TERMS.items():
                    if not any(term in lower_text for term in terms):
                        continue
                    concept_id = "product-concept:" + slug(concept_label)
                    connection.execute(
                        "INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)",
                        (concept_id, "product_concept", concept_label, "public_product", "{}"),
                    )
                    connection.execute(
                        "INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)",
                        (source_id, "COVERS", concept_id, 1.0, source_id),
                    )
            for index, part in enumerate(chunks(text)):
                chunk_id = f"{source_id}:chunk:{index}"
                connection.execute("INSERT INTO chunks VALUES (?,?,?,?,?)", (chunk_id, source_id, index, level, part))
                connection.execute("INSERT INTO chunks_fts VALUES (?,?,?)", (part, source_id, level))
                if can_export_public_text(path, level):
                    public_text = redact(part)
                    public_hash = hashlib.sha256(public_text.encode()).hexdigest()
                    if public_hash not in public_chunk_hashes:
                        public_chunk_hashes.add(public_hash)
                        public_source = "Credit Risk Papers" if level == "public_theory" else redact(path.stem)
                        public_chunks.append({"id": chunk_id, "source": public_source, "source_id": source_id, "access": level, "text": public_text})
            if path.suffix.lower() == ".md" and text:
                source_node = "page:" + slug(path.stem)
                connection.execute("INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)", (source_node, "page", path.stem, level, "{}"))
                connection.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)", (source_id, "REPRESENTS", source_node, 1.0, source_id))
                links = [normalize(link) for link in WIKILINK_RE.findall(text)]
                for target in links:
                    target_node = "page:" + slug(target)
                    connection.execute("INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)", (target_node, "concept", target, level, "{}"))
                    concept_edges[(source_node, "LINKS_TO", target_node, source_id)] += 1
        except Exception as exc:
            manifest.append({"path": str(path), "error": type(exc).__name__})

    for (source_node, relation, target_node, evidence), weight in concept_edges.items():
        connection.execute("INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?)", (source_node, relation, target_node, float(weight), evidence))

    oscar_texts: list[str] = []
    voice_examples: list[dict] = []
    meeting_count = 0
    utterance_count = 0
    oscar_utterance_count = 0
    meeting_artifact_count = 0

    for meeting in meetings:
        # Los nombres de reuniones, asistentes y dominios nunca llegan al artefacto público.
        meeting_id = "meeting:" + str(meeting.get("recording_id") or hashlib.sha256(str(meeting.get("url", "")).encode()).hexdigest()[:20])
        transcript = meeting.get("transcript") or []
        oscar_count = sum(is_oscar(item.get("speaker")) for item in transcript if isinstance(item, dict))
        safe_title = f"Reunión {meeting_count + 1}"
        connection.execute(
            "INSERT INTO meetings VALUES (?,?,?,?,?,?)",
            (meeting_id, safe_title, meeting.get("created_at"), len(transcript), oscar_count, json.dumps({"recording_id": meeting.get("recording_id")}, ensure_ascii=False)),
        )
        connection.execute("INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)", (meeting_id, "meeting", safe_title, "private_voice", "{}"))
        meeting_count += 1
        for artifact_type in ("default_summary", "action_items", "highlights"):
            value = meeting.get(artifact_type)
            if not value:
                continue
            artifact_text = normalize(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
            if not artifact_text:
                continue
            artifact_id = f"{meeting_id}:artifact:{artifact_type}"
            connection.execute("INSERT INTO meeting_artifacts VALUES (?,?,?,?)", (artifact_id, meeting_id, artifact_type, artifact_text))
            connection.execute("INSERT INTO meeting_artifacts_fts VALUES (?,?,?)", (artifact_text, meeting_id, artifact_type))
            connection.execute("INSERT OR IGNORE INTO nodes VALUES (?,?,?,?,?)", (artifact_id, "meeting_artifact", artifact_type, "private_voice", "{}"))
            connection.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)", (meeting_id, "HAS_ARTIFACT", artifact_id, 1.0, meeting_id))
            meeting_artifact_count += 1
        for index, item in enumerate(transcript):
            if not isinstance(item, dict):
                continue
            text = normalize(str(item.get("text", "")))
            if not text:
                continue
            role = "oscar" if is_oscar(item.get("speaker")) else "other"
            utterance_id = f"{meeting_id}:utterance:{index}"
            connection.execute("INSERT INTO utterances VALUES (?,?,?,?,?)", (utterance_id, meeting_id, role, str(item.get("timestamp", "")), text))
            connection.execute("INSERT INTO utterances_fts VALUES (?,?,?)", (text, meeting_id, role))
            utterance_count += 1
            if role == "oscar":
                oscar_utterance_count += 1
                oscar_texts.append(text)
                example = safe_voice_example(text)
                if example and len(voice_examples) < 600:
                    voice_examples.append({"text": example, "meeting_id": meeting_id})

    corpus = " ".join(oscar_texts).lower()
    words = WORD_RE.findall(corpus)
    word_freq = Counter(words)
    bigrams = Counter(zip(words, words[1:]))
    trigrams = Counter(zip(words, words[1:], words[2:]))
    markers = Counter({marker: len(re.findall(r"\b" + re.escape(marker) + r"\b", corpus)) for marker in DISCOURSE})
    verb_forms = Counter({word: count for word, count in word_freq.items() if len(word) >= 4 and word.endswith(VERB_ENDINGS)})
    utterance_lengths = [len(WORD_RE.findall(text)) for text in oscar_texts]
    total_words = len(words)

    def store_features(kind: str, values: Counter, limit: int | None = None) -> None:
        pairs = values.most_common(limit)
        for feature, count in pairs:
            label = " ".join(feature) if isinstance(feature, tuple) else str(feature)
            connection.execute(
                "INSERT OR REPLACE INTO style_features VALUES (?,?,?,?)",
                (kind, label, int(count), (count / total_words * 1000) if total_words else 0.0),
            )

    store_features("word", word_freq)
    store_features("bigram", bigrams)
    store_features("trigram", trigrams)
    store_features("discourse_marker", markers)
    store_features("verb_surface_form", verb_forms)

    profile = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "estilo oral de Oscar; nunca fuente factual",
        "statistics": {
            "meetings": meeting_count,
            "utterances_total": utterance_count,
            "oscar_utterances": oscar_utterance_count,
            "oscar_words": total_words,
            "vocabulary": len(word_freq),
            "unique_bigrams": len(bigrams),
            "unique_trigrams": len(trigrams),
            "verb_surface_forms": len(verb_forms),
            "average_utterance_words": round(sum(utterance_lengths) / len(utterance_lengths), 2) if utterance_lengths else 0,
        },
        # El perfil desplegable no contiene vocabulario temático ni frases literales.
        # El léxico y combinaciones completos permanecen en SQLite privado.
        "top_words": [],
        "top_bigrams": [],
        "top_trigrams": [],
        "discourse_markers": [{"text": marker, "count": count} for marker, count in markers.most_common() if count],
        "verb_surface_forms": [],
        "conjugation_profile": [
            {"ending": ending, "count": sum(count for word, count in verb_forms.items() if word.endswith(ending))}
            for ending in VERB_ENDINGS
        ],
        "voice_rules": [
            "Responder en español conversacional, directo y pedagógico.",
            "Empezar por la idea central y luego explicar el porqué con un ejemplo aplicado.",
            "Usar marcadores reales de Oscar solo cuando encajen; no convertirlos en muletillas artificiales.",
            "No atribuir a Oscar frases literales que no estén en el corpus.",
            "La voz define forma; los hechos salen exclusivamente de fuentes públicas autorizadas con procedencia.",
        ],
    }

    exported_source_ids = {item["source_id"] for item in public_chunks}
    graph_terms = {
        "credit", "risk", "riesgo", "score", "scorecard", "default", "pd", "lgd", "ead",
        "loss", "pérdida", "capital", "validation", "validación", "logistic", "logit",
        "portfolio", "cartera", "pricing", "collections", "cobranza", "sarc", "calibration",
        "backtesting", "scoring", "model", "modelo", "lifecycle", "ciclo", "retail", "microfinance",
    }
    public_nodes = []
    for node_id, kind, label, level in connection.execute(
        "SELECT id,kind,label,access_level FROM nodes WHERE access_level IN ('public_theory','public_product')"
    ):
        normalized_label = set(WORD_RE.findall(label.lower()))
        include_product = level == "public_product" and (node_id in exported_source_ids or kind == "product_concept")
        include_theory = level == "public_theory" and kind in {"concept", "page"} and bool(normalized_label & graph_terms)
        if include_product or include_theory:
            public_nodes.append({"id": node_id, "kind": kind, "label": redact(label), "access": level})
    allowed_ids = {node["id"] for node in public_nodes}
    public_edges = [
        {"source": row[0], "relation": row[1], "target": row[2], "weight": row[3], "evidence": row[4]}
        for row in connection.execute("SELECT source_id,relation,target_id,weight,evidence_source FROM edges")
        if row[0] in allowed_ids and row[2] in allowed_ids
    ]

    connection.commit()
    connection.close()
    os.chmod(db_build_path, 0o600)
    os.replace(db_build_path, DB_PATH)

    (OUT / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    style_tmp = EXPORT / "style_profile.json.tmp"
    style_tmp.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    # Los ejemplos literales permanecen privados; producción usa estadísticas agregadas.
    with (OUT / "voice_examples_private.jsonl").open("w", encoding="utf-8") as handle:
        for item in voice_examples:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    corpus_tmp = EXPORT / "public_corpus.jsonl.tmp"
    with corpus_tmp.open("w", encoding="utf-8") as handle:
        for item in public_chunks:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    graph_tmp = EXPORT / "knowledge_graph.json.tmp"
    graph_tmp.write_text(json.dumps({"nodes": public_nodes, "edges": public_edges}, ensure_ascii=False), encoding="utf-8")
    os.replace(style_tmp, EXPORT / "style_profile.json")
    os.replace(corpus_tmp, EXPORT / "public_corpus.jsonl")
    os.replace(graph_tmp, EXPORT / "knowledge_graph.json")

    summary = {
        "files_in_manifest": len(manifest),
        "documents_extracted": extracted_docs,
        "document_words": extracted_words,
        "public_chunks": len(public_chunks),
        "graph_nodes_public": len(public_nodes),
        "graph_edges_public": len(public_edges),
        **profile["statistics"],
        "voice_examples": len(voice_examples),
        "meeting_artifacts": meeting_artifact_count,
        "database": str(DB_PATH),
    }
    (OUT / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
