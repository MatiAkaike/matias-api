import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import presentacion_acceso as pa


def correr(coro):
    return asyncio.run(coro)


class ValidacionTests(unittest.TestCase):
    def test_nombre(self):
        self.assertIsNone(pa.validar_nombre("Laura Pérez")[1])
        self.assertIsNotNone(pa.validar_nombre("x")[1])
        self.assertIsNotNone(pa.validar_nombre("<script>")[1])
        self.assertEqual(pa.validar_nombre("  Ana   María  ")[0], "Ana María")

    def test_whatsapp_por_pais(self):
        self.assertEqual(pa.validar_whatsapp("300 123 4567", "CO"), ("573001234567", None))
        self.assertEqual(pa.validar_whatsapp("+52 55 6912 1683", "CO")[0], "525569121683")
        self.assertIsNotNone(pa.validar_whatsapp("123", "CO")[1])
        self.assertIsNotNone(pa.validar_whatsapp("601 234 5678", "CO")[1])  # fijo de Bogotá, no celular
        self.assertIsNotNone(pa.validar_whatsapp("abc", "CO")[1])

    def test_correo_formato_y_desechables(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)):
            self.assertIsNone(correr(pa.validar_correo("Laura@Entidad.com.co"))[1])
            self.assertEqual(correr(pa.validar_correo(" Laura@Entidad.com.co "))[0], "laura@entidad.com.co")
            self.assertIsNotNone(correr(pa.validar_correo("laura@"))[1])
            self.assertIsNotNone(correr(pa.validar_correo("laura..p@entidad.com"))[1])
            self.assertIsNotNone(correr(pa.validar_correo("x@mailinator.com"))[1])
            self.assertIsNone(correr(pa.validar_correo("alguien@gmail.com"))[1])

    def test_correo_dominio_sin_mx(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=False)):
            self.assertIn("dominio", correr(pa.validar_correo("laura@no-existe-akaike-xyz.com"))[1])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        import server
        self.server = server
        self.client = TestClient(server.app)  # sin lifespan: no toca la base real
        import anti_bots, base64, hashlib, json
        def cab():
            r = anti_bots.emitir_reto(); r["emitido"] -= 10
            r["firma"] = anti_bots._firma(r["salt"], r["reto"], r["expira"], r["emitido"])
            n = next(n for n in range(r["max"] + 1) if hashlib.sha256(f"{r['salt']}{n}".encode()).hexdigest() == r["reto"])
            return {"Origin": "https://www.akaike.lat", "X-Reto": base64.b64encode(json.dumps({**r, "numero": n}).encode()).decode()}
        self.cab = cab

    def test_lead_valido_se_guarda(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)), \
             patch.object(pa, "guardar_lead", AsyncMock()) as guardar, \
             patch.object(self.server.database, "log_presentation_event", AsyncMock()):
            r = self.client.post("/api/presentacion/lead", headers=self.cab(), json={
                "session_id": "pres-prueba-1", "nombre": "Laura Pérez", "correo": "laura@entidad.com",
                "whatsapp": "3001234567", "pais": "CO", "autoriza_datos": True, "origen": "linkedin"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True, "nombre": "Laura"})
        args = guardar.call_args.args
        self.assertEqual(args[:5], ("pres-prueba-1", "Laura Pérez", "laura@entidad.com", "573001234567", "CO"))

    def test_lead_guardado_responde_ok_aunque_falle_el_evento(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)), \
             patch.object(pa, "guardar_lead", AsyncMock()) as guardar, \
             patch.object(self.server.database, "log_presentation_event", AsyncMock(side_effect=RuntimeError("CHECK event_type"))):
            r = self.client.post("/api/presentacion/lead", headers=self.cab(), json={
                "session_id": "pres-prueba-3", "nombre": "Laura Pérez", "correo": "laura@entidad.com",
                "whatsapp": "3001234567", "pais": "CO", "autoriza_datos": True})
        self.assertEqual(r.json(), {"ok": True, "nombre": "Laura"})
        guardar.assert_called_once()

    def test_lead_invalido_devuelve_errores_por_campo(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)), \
             patch.object(pa, "guardar_lead", AsyncMock()) as guardar:
            r = self.client.post("/api/presentacion/lead", headers=self.cab(), json={
                "session_id": "pres-prueba-2", "nombre": "L", "correo": "malo", "whatsapp": "12",
                "pais": "CO", "autoriza_datos": False})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()["errores"]), {"nombre", "correo", "whatsapp", "autoriza_datos"})
        guardar.assert_not_called()

    def test_enlace_personal(self):
        with patch.object(pa, "usar_enlace", AsyncMock(return_value=("Banco Demo", "ok"))):
            self.assertEqual(self.client.get("/api/presentacion/acceso?p=abcdefgh123").json(), {"valido": True, "cliente": "Banco Demo", "motivo": "ok"})
        with patch.object(pa, "usar_enlace", AsyncMock(return_value=(None, "limite"))) as usar:
            self.assertEqual(self.client.get("/api/presentacion/acceso?p=abcdefgh123").json(), {"valido": False, "cliente": "", "motivo": "limite"})
            self.assertEqual(usar.call_args.args[0], "abcdefgh123")  # la IP del visitante va como segundo argumento

    def test_token_con_formato_invalido_no_consulta_la_base(self):
        self.assertEqual(asyncio.run(pa.usar_enlace("x", "1.2.3.4")), (None, "invalido"))

    def test_desactivar_exige_token_admin(self):
        r = self.client.post("/api/admin/presentacion/enlaces/abcdefgh123/desactivar")
        self.assertIn(r.status_code, (401, 503))

    def test_crear_enlaces_exige_token_admin(self):
        r = self.client.post("/api/admin/presentacion/enlaces", json={"cliente": "Banco Demo"})
        self.assertIn(r.status_code, (401, 503))


class RedesInternasTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        import server
        self.server = server
        self.client = TestClient(server.app)
        pa._redes_cache = (0.0, [])

    def tearDown(self):
        pa._redes_cache = (0.0, [])

    def test_normalizar_red(self):
        self.assertEqual(pa.normalizar_red("206.62.142.99/24"), "206.62.142.0/24")
        self.assertEqual(pa.normalizar_red("206.62.142.99"), "206.62.142.99/32")
        with self.assertRaises(ValueError):
            pa.normalizar_red("0.0.0.0/0")
        with self.assertRaises(ValueError):
            pa.normalizar_red("no-es-ip")

    def test_es_interna_por_variable(self):
        with patch.dict("os.environ", {"PRESENTACION_REDES_INTERNAS": "206.62.142.0/24"}), \
             patch.object(pa.database, "_get_pg_pool", AsyncMock(return_value=None)):
            self.assertTrue(asyncio.run(pa.es_interna("206.62.142.254")))
            self.assertFalse(asyncio.run(pa.es_interna("206.62.143.1")))
            self.assertFalse(asyncio.run(pa.es_interna("basura")))

    def test_acceso_interno_no_gasta_ip_del_enlace(self):
        with patch.object(pa, "es_interna", AsyncMock(return_value=True)), \
             patch.object(pa, "usar_enlace", AsyncMock()) as usar:
            d = self.client.get("/api/presentacion/acceso?p=abcdefgh123").json()
        self.assertEqual(d, {"valido": True, "cliente": "Akaike", "motivo": "interno", "interno": True})
        usar.assert_not_called()

    def test_eventos_internos_no_se_registran(self):
        with patch.object(pa, "es_interna", AsyncMock(return_value=True)), \
             patch.object(self.server.database, "log_presentation_event", AsyncMock()) as log:
            r = self.client.post("/api/presentacion/event", json={"session_id": "pres-x", "event_type": "slide_view", "slide": 1})
        self.assertEqual(r.json(), {"ok": True})
        log.assert_not_called()

    def test_turno_interno_no_se_persiste(self):
        req = self.server.PresentacionRequest(message="hola", session_id="pres-interno", interno=True)
        with patch.object(self.server.database, "log_interaction", AsyncMock()) as log, \
             patch.object(self.server.database, "_get_pg_pool", AsyncMock(return_value=None)):
            r = asyncio.run(self.server._persist_presentation_turn(req, "respuesta", "grafo_publico", "206.62.142.1", "ua"))
        self.assertEqual(r.reply.strip()[:9], "respuesta")
        log.assert_not_called()

    def test_redes_internas_exigen_token_admin(self):
        self.assertIn(self.client.get("/api/admin/presentacion/redes-internas").status_code, (401, 503))
        self.assertIn(self.client.post("/api/admin/presentacion/redes-internas", json={"red": "1.2.3.0/24"}).status_code, (401, 503))


if __name__ == "__main__":
    unittest.main()
