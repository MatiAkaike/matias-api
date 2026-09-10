"""Pruebas del grafo público y la capa de voz agregada."""

import asyncio
import json
import re
from pathlib import Path

import oscar_graph_runtime
import server
from fastapi.testclient import TestClient


BASE = Path(__file__).resolve().parent / "oscar_graph"


def test_busqueda_crediticia_tiene_procedencia_y_usa_grafo():
    context, sources = oscar_graph_runtime.search("¿Cómo se valida un modelo de credit scoring?")
    assert context
    assert sources
    assert "FUENTE" in context
    assert "RELACIONES DEL GRAFO" in context
    assert "Grafo de conocimiento Akaike" in sources


def test_consulta_fuera_de_dominio_no_recupera_precio_de_matias():
    context, sources = oscar_graph_runtime.search("¿Cuál es el precio de bitcoin?")
    assert context == ""
    assert sources == []


def test_estilo_es_agregado_y_no_factual():
    prompt = oscar_graph_runtime.style_prompt()
    assert "únicamente la forma" in prompt
    assert "No aport" in prompt
    assert "@akaike.co" not in prompt


def test_export_publico_no_contiene_contactos_ni_terceros():
    lines = (BASE / "public_corpus.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    texts = "\n".join(row["text"] for row in rows)
    assert not re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", texts)
    phone_candidates = re.findall(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", texts)
    assert not [candidate for candidate in phone_candidates if len(re.findall(r"\d", candidate)) >= 9]
    assert all(row["source"] == "Credit Risk Papers" for row in rows if row["access"] == "public_theory")
    for third_party in ("experian", "transunion", "datacredito", "upstart", "masschallenge"):
        assert third_party not in texts.lower()


def test_grafo_tiene_solo_niveles_publicos():
    graph = json.loads((BASE / "knowledge_graph.json").read_text(encoding="utf-8"))
    assert graph["nodes"]
    assert all(node["access"] in {"public_theory", "public_product"} for node in graph["nodes"])


def test_perfil_declara_tamaño_del_corpus():
    profile = json.loads((BASE / "style_profile.json").read_text(encoding="utf-8"))
    stats = profile["statistics"]
    assert stats["meetings"] > 0
    assert stats["oscar_utterances"] > 0
    assert stats["oscar_words"] > 0


def test_sanitizador_publico_remueve_contactos_y_autores():
    raw = "Según Nombre Apellido, escriba a persona@example.com o llame al +57 300 123 4567."
    clean = server._sanitize_public_reply(raw)
    assert "Nombre Apellido" not in clean
    assert "persona@example.com" not in clean
    assert "+57 300 123 4567" not in clean
    assert server._sanitize_public_reply("Lo aclaro con precisión") == "Lo aclaro con precisión"
    assert len(server._sanitize_public_reply(" ".join(["palabra"] * 121)).split()) <= 120


def test_endpoint_se_abstiene_fuera_del_dominio_y_valida_tamano():
    with server._chat_quota_lock:
        server._chat_quota.clear()
    client = TestClient(server.app)
    response = client.post(
        "/api/presentacion",
        json={"message": "¿Cuál es el clima en Bogotá?", "session_id": "qa", "slide": -1},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "sin_fuente"
    assert "riesgo de crédito" in response.json()["reply"]
    assert "calendar.app.google" in response.json()["reply"]
    oversized = client.post(
        "/api/presentacion",
        json={"message": "x" * 2001, "session_id": "qa", "slide": -1},
    )
    assert oversized.status_code == 422
    with_slide = client.post(
        "/api/presentacion",
        json={"message": "¿Cuál es el clima en Bogotá?", "session_id": "qa-slide", "slide": 0},
    )
    assert with_slide.status_code == 200
    assert with_slide.json()["source"] == "sin_fuente"
    false_demo = client.post(
        "/api/presentacion",
        json={"message": "¿Qué es la democracia?", "session_id": "qa-demo", "slide": 0},
    )
    assert false_demo.status_code == 200
    assert false_demo.json()["source"] == "sin_fuente"


def test_cors_presentacion_permite_akaike_y_rechaza_origen_externo():
    client = TestClient(server.app)
    headers = {"Access-Control-Request-Method": "POST"}
    allowed = client.options("/api/presentacion", headers={**headers, "Origin": "https://akaike.lat"})
    blocked = client.options("/api/presentacion", headers={**headers, "Origin": "https://evil.example"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://akaike.lat"
    assert blocked.status_code == 400


def test_profundizacion_tecnica_redirige_a_agenda_sin_detalles():
    client = TestClient(server.app)
    response = client.post(
        "/api/presentacion",
        json={"message": "dime paso a paso como debo construirlo", "session_id": "qa-tec", "slide": -1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "agenda"
    assert "calendar.app.google" in body["reply"]
    assert "GINI" not in body["reply"] and "PD" not in body["reply"]


def test_pregunta_comercial_no_dispara_redireccion_tecnica():
    client = TestClient(server.app)
    response = client.post(
        "/api/presentacion",
        json={"message": "¿Cómo funciona M.A.T.I.A.S.?", "session_id": "qa-com", "slide": -1},
    )
    assert response.status_code == 200
    assert response.json()["source"] != "agenda"


def test_turno_presentacion_persiste_chat_evento_y_lead(monkeypatch):
    calls = []
    transaction_events = []

    async def fake_log_interaction(session_id, role, content, model=None, source="web", conn=None):
        calls.append(("interaction", session_id, role, source, model, content, conn))

    async def fake_save_lead(session_id, text, ip="", source="", conn=None):
        calls.append(("lead", session_id, source, ip, text, conn))
        return {"session_id": session_id}

    async def fake_log_event(**kwargs):
        calls.append(("event", kwargs))

    class Transaction:
        async def __aenter__(self):
            transaction_events.append("begin")

        async def __aexit__(self, exc_type, *_args):
            transaction_events.append("commit" if exc_type is None else "rollback")

    class Connection:
        def transaction(self):
            return Transaction()

    transaction_conn = Connection()

    class Acquire:
        async def __aenter__(self):
            return transaction_conn

        async def __aexit__(self, *_args):
            return False

    class Pool:
        def acquire(self):
            return Acquire()

    async def fake_get_pool():
        return Pool()

    monkeypatch.setattr(server.database, "log_interaction", fake_log_interaction)
    monkeypatch.setattr(server.database, "log_presentation_event", fake_log_event)
    monkeypatch.setattr(server.database, "_get_pg_pool", fake_get_pool)
    monkeypatch.setattr(server.leads, "save_lead", fake_save_lead)
    req = server.PresentacionRequest(
        message="Soy Ana, mi correo es ana@example.com",
        session_id="qa-persistencia",
        slide=5,
    )

    result = asyncio.run(
        server._persist_presentation_turn(
            req,
            "Respuesta verificada",
            "grafo_publico",
            "127.0.0.1",
            "pytest",
            ["Grafo de conocimiento Akaike"],
        )
    )

    interactions = [call for call in calls if call[0] == "interaction"]
    assert [call[2] for call in interactions] == ["user", "assistant"]
    assert all(call[3] == "presentacion" for call in interactions)
    lead = next(call for call in calls if call[0] == "lead")
    assert lead[2] == "Presentación M.A.T.I.A.S."
    event = next(call for call in calls if call[0] == "event")[1]
    assert event["event_type"] == "question"
    assert event["data"]["reply"] == "Respuesta verificada"
    assert transaction_events == ["begin", "commit"]
    assert all(call[-1] is transaction_conn for call in interactions)
    assert lead[-1] is transaction_conn
    assert event["conn"] is transaction_conn
    assert result.source == "grafo_publico"


def test_cuota_de_chat_se_agota_tras_10_mensajes():
    client = TestClient(server.app)
    with server._chat_quota_lock:
        server._chat_quota.clear()
    server.rate_tracker.clear()
    for i in range(10):
        response = client.post(
            "/api/presentacion",
            json={"message": f"mensaje {i}", "session_id": "quota", "slide": -1},
        )
        assert response.status_code == 200
        assert response.json()["source"] != "cuota"
    agotado = client.post(
        "/api/presentacion",
        json={"message": "mensaje 11", "session_id": "quota", "slide": -1},
    )
    assert agotado.status_code == 200
    body = agotado.json()
    assert body["source"] == "cuota"
    assert "cuota" in body["reply"].lower()
    assert "calendar.app.google" in body["reply"]
