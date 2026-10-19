import base64, hashlib, json, time, unittest
from unittest.mock import AsyncMock, patch

import anti_bots as ab


def resolver(r, numero=None):
    if numero is None:
        numero = next(n for n in range(r["max"] + 1) if hashlib.sha256(f"{r['salt']}{n}".encode()).hexdigest() == r["reto"])
    return base64.b64encode(json.dumps({**r, "numero": numero}).encode()).decode()


class RetoTests(unittest.TestCase):
    def test_reto_resuelto_sirve_una_sola_vez(self):
        r = ab.emitir_reto(); cab = resolver(r)
        self.assertEqual(ab.verificar(cab), (True, "ok"))
        self.assertEqual(ab.verificar(cab), (False, "repetido"))

    def test_solucion_incorrecta_firma_y_vencimiento(self):
        r = ab.emitir_reto()
        self.assertEqual(ab.verificar(resolver(r, numero=-1)), (False, "solucion"))
        malo = {**r, "reto": "0" * 64}
        self.assertEqual(ab.verificar(base64.b64encode(json.dumps({**malo, "numero": 1}).encode()).decode()), (False, "firma"))
        self.assertEqual(ab.verificar(""), (False, "sin_reto"))
        with patch.object(ab.time, "time", return_value=time.time() + ab.VIGENCIA + 5):
            self.assertEqual(ab.verificar(resolver(r))[1], "vencido")

    def test_edad_minima(self):
        r = ab.emitir_reto()
        self.assertEqual(ab.verificar(resolver(r), edad_minima=3), (False, "rapido"))

    def test_origen(self):
        self.assertTrue(ab.origen_valido("https://www.akaike.lat"))
        self.assertTrue(ab.origen_valido("", "https://akaike.lat/presentacion/"))
        self.assertFalse(ab.origen_valido("https://evil.example"))
        self.assertFalse(ab.origen_valido("", ""))

    def test_tope_global(self):
        with patch.object(ab, "TOPE_HORA", 2):
            ab._respuestas.clear()
            self.assertTrue(ab.hay_cupo_global()); self.assertTrue(ab.hay_cupo_global()); self.assertFalse(ab.hay_cupo_global())
            ab._respuestas.clear()


class EndpointTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        import server
        self.server = server
        self.c = TestClient(server.app)
        self.h = {"Origin": "https://www.akaike.lat"}

    def test_chat_sin_reto_o_sin_origen_se_rechaza(self):
        body = {"message": "hola", "session_id": "pres-abc"}
        self.assertEqual(self.c.post("/api/presentacion", json=body).json(), {"detail": "origen"})
        r = self.c.post("/api/presentacion", json=body, headers=self.h)
        self.assertEqual((r.status_code, r.json()["detail"]), (403, "reto"))

    def test_reto_solo_desde_akaike(self):
        self.assertEqual(self.c.post("/api/presentacion/reto").status_code, 403)
        r = self.c.post("/api/presentacion/reto", headers=self.h).json()
        self.assertEqual(set(r) >= {"salt", "reto", "max", "firma", "emitido", "expira"}, True)

    def test_lead_trampa_no_guarda(self):
        r = ab.emitir_reto(); r["emitido"] -= 10; r["firma"] = ab._firma(r["salt"], r["reto"], r["expira"], r["emitido"])
        with patch("presentacion_acceso.guardar_lead", AsyncMock()) as guardar:
            res = self.c.post("/api/presentacion/lead", headers={**self.h, "X-Reto": resolver(r)}, json={
                "session_id": "pres-abc123", "nombre": "Bot", "correo": "b@x.com", "whatsapp": "1", "pais": "CO",
                "autoriza_datos": True, "sitio_web": "http://spam"})
        self.assertEqual(res.json(), {"ok": True, "nombre": ""})
        guardar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
