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

    def test_lead_valido_se_guarda(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)), \
             patch.object(pa, "guardar_lead", AsyncMock()) as guardar, \
             patch.object(self.server.database, "log_presentation_event", AsyncMock()):
            r = self.client.post("/api/presentacion/lead", json={
                "session_id": "pres-prueba-1", "nombre": "Laura Pérez", "correo": "laura@entidad.com",
                "whatsapp": "3001234567", "pais": "CO", "autoriza_datos": True, "origen": "linkedin"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True, "nombre": "Laura"})
        args = guardar.call_args.args
        self.assertEqual(args[:5], ("pres-prueba-1", "Laura Pérez", "laura@entidad.com", "573001234567", "CO"))

    def test_lead_invalido_devuelve_errores_por_campo(self):
        with patch.object(pa, "_dominio_recibe_correo", AsyncMock(return_value=True)), \
             patch.object(pa, "guardar_lead", AsyncMock()) as guardar:
            r = self.client.post("/api/presentacion/lead", json={
                "session_id": "pres-prueba-2", "nombre": "L", "correo": "malo", "whatsapp": "12",
                "pais": "CO", "autoriza_datos": False})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.json()["errores"]), {"nombre", "correo", "whatsapp", "autoriza_datos"})
        guardar.assert_not_called()

    def test_enlace_personal(self):
        with patch.object(pa, "usar_enlace", AsyncMock(return_value="Banco Demo")):
            self.assertEqual(self.client.get("/api/presentacion/acceso?p=abcdefgh123").json(), {"valido": True, "cliente": "Banco Demo"})
        with patch.object(pa, "usar_enlace", AsyncMock(return_value=None)):
            self.assertEqual(self.client.get("/api/presentacion/acceso?p=x").json(), {"valido": False, "cliente": ""})

    def test_crear_enlaces_exige_token_admin(self):
        r = self.client.post("/api/admin/presentacion/enlaces", json={"cliente": "Banco Demo"})
        self.assertIn(r.status_code, (401, 503))


if __name__ == "__main__":
    unittest.main()
