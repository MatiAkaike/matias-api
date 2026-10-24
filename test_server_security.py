import unittest
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError
from starlette.requests import Request

import server


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        server.rate_tracker.clear()

    def test_rate_limit_returns_false_after_limit(self):
        self.assertTrue(server._allow_request("203.0.113.10", "chat", 2))
        self.assertTrue(server._allow_request("203.0.113.10", "chat", 2))
        self.assertFalse(server._allow_request("203.0.113.10", "chat", 2))

    def test_uses_rightmost_public_forwarded_ip_behind_private_proxy(self):
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"198.51.100.9, 8.8.8.8")],
            "client": ("10.0.0.2", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        })
        self.assertEqual(server._get_client_ip(request), "8.8.8.8")

    def _request_con_xff(self, xff: str, peer: str = "10.0.0.2"):
        return Request({
            "type": "http", "method": "GET", "path": "/",
            "headers": [(b"x-forwarded-for", xff.encode())],
            "client": (peer, 1234), "server": ("test", 80), "scheme": "http", "query_string": b"",
        })

    def test_ip_inventada_por_el_cliente_no_cuenta(self):
        # Aviso del 24-oct-2026: con la red interna de Akaike escrita a la izquierda, Uvicorn la
        # ponía en request.client y la API la creía. Cuenta la que agregó la infraestructura.
        request = self._request_con_xff("206.62.142.10, 190.85.1.2", peer="206.62.142.10")
        self.assertEqual(server._get_client_ip(request), "190.85.1.2")

    def test_la_ip_de_cloudflare_a_la_derecha_se_salta(self):
        request = self._request_con_xff("206.62.142.10, 190.85.1.2, 172.70.10.5", peer="206.62.142.10")
        self.assertEqual(server._get_client_ip(request), "190.85.1.2")
        request = self._request_con_xff("190.85.1.2, 2606:4700::1")
        self.assertEqual(server._get_client_ip(request), "190.85.1.2")

    def test_sin_forwarded_usa_la_conexion(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/", "headers": [],
            "client": ("190.85.1.2", 1234), "server": ("test", 80), "scheme": "http", "query_string": b"",
        })
        self.assertEqual(server._get_client_ip(request), "190.85.1.2")
        self.assertEqual(server._get_client_ip(self._request_con_xff("basura, 10.0.0.9")), "10.0.0.2")

    def test_cuota_diaria_del_chat_web(self):
        server._web_chat_quota.clear()
        with patch.object(server, "WEB_CHAT_QUOTA_LIMIT", 2):
            self.assertTrue(server._consume_web_chat_quota("190.85.1.2"))
            self.assertTrue(server._consume_web_chat_quota("190.85.1.2"))
            self.assertFalse(server._consume_web_chat_quota("190.85.1.2"))
            self.assertTrue(server._consume_web_chat_quota("190.85.1.3"))
        server._web_chat_quota.clear()

    def test_request_models_reject_oversized_fields(self):
        with self.assertRaises(ValidationError):
            server.ChatRequest(message="x" * 4001)
        with self.assertRaises(ValidationError):
            server.AnalyticsEvent(
                session_id="session",
                event_type="click",
                metadata="x" * 4001,
            )

    def test_analytics_models_default_consent_false(self):
        # Sin consentimiento explícito, la analítica NO se captura.
        pv = server.AnalyticsPageView(session_id="s", url="https://akaike.lat/")
        self.assertFalse(pv.consent)
        ev = server.AnalyticsEvent(session_id="s", event_type="click")
        self.assertFalse(ev.consent)


class ClientContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_ip_geo_and_user_agent_from_trusted_headers(self):
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", b"8.8.8.8"),
                (b"user-agent", b"Mozilla/5.0 Test"),
                (b"x-vercel-ip-country", b"CO"),
                (b"x-vercel-ip-country-region", b"ANT"),
                (b"x-vercel-ip-city", b"Medell%C3%ADn"),
                (b"x-vercel-ip-latitude", b"6.2442"),
                (b"x-vercel-ip-longitude", b"-75.5812"),
            ],
            "client": ("10.0.0.2", 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        })
        with patch.dict("os.environ", {"TRUST_EDGE_GEO_HEADERS": "true"}):
            context = await server._get_client_context(request)
        self.assertEqual(context["ip"], "8.8.8.8")
        self.assertEqual(context["country"], "CO")
        self.assertEqual(context["region"], "ANT")
        self.assertEqual(context["city"], "Medellín")
        self.assertEqual(context["user_agent"], "Mozilla/5.0 Test")
        self.assertEqual(context["latitude"], 6.2442)
        self.assertEqual(context["longitude"], -75.5812)

    async def test_ignores_spoofed_geo_headers_by_default(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/",
            "headers": [(b"cf-ipcountry", b"XX"), (b"x-vercel-ip-city", b"Fake")],
            "client": ("8.8.8.8", 1234), "server": ("test", 80),
            "scheme": "http", "query_string": b"",
        })
        with patch.dict("os.environ", {"GEOIP_LOOKUP_ENABLED": "false"}):
            context = await server._get_client_context(request)
        self.assertEqual(context["country"], "unknown")
        self.assertEqual(context["city"], "")

    async def test_analytics_failure_does_not_break_chat_path(self):
        with patch.object(server.analytics_store, "touch_session", side_effect=RuntimeError("db down")):
            await server._touch_session_safe("qa-session", {"ip": "8.8.8.8"})

    async def test_chat_preserves_frontend_session_id(self):
        sid = "web-qa-linked-session"
        request = Request({
            "type": "http", "method": "POST", "path": "/api/chat", "headers": [],
            "client": ("127.0.0.1", 1234), "server": ("test", 80),
            "scheme": "http", "query_string": b"",
        })
        server.sessions.pop(sid, None)
        with (
            patch.object(server.database, "get_session_interactions", new=AsyncMock(return_value=[])),
            patch.object(server.database, "log_interaction", new=AsyncMock()),
            patch.object(server.leads, "save_lead", new=AsyncMock()),
            patch.object(server, "_touch_session_safe", new=AsyncMock()),
        ):
            response = await server._chat_impl(server.ChatRequest(message="quiero agendar", session_id=sid), request)
        self.assertEqual(response.session_id, sid)


class SecurityMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        server.rate_tracker.clear()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_chat_returns_429_after_limit(self):
        for _ in range(20):
            server._allow_request("127.0.0.1", "chat", 20)
        response = await self.client.post("/api/chat", json={"message": "hola"})
        self.assertEqual(response.status_code, 429)

    async def test_operations_status_is_not_public(self):
        response = await self.client.get("/api/operations/status")
        self.assertIn(response.status_code, (401, 503))

    async def test_signals_report_is_not_public(self):
        response = await self.client.get("/api/analytics/signals")
        self.assertIn(response.status_code, (401, 503))

    async def test_large_body_is_rejected_before_route(self):
        response = await self.client.post(
            "/api/analytics/event",
            content=b"{}",
            headers={"content-length": "70000"},
        )
        self.assertEqual(response.status_code, 413)

    async def test_pageview_without_consent_is_not_stored(self):
        with patch.object(server.analytics_store, "log_page_view", new=AsyncMock()) as mock_log:
            response = await self.client.post(
                "/api/analytics/pageview",
                json={"session_id": "s1", "url": "https://akaike.lat/", "consent": False},
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["accepted"])
            mock_log.assert_not_awaited()

    async def test_pageview_with_consent_is_stored(self):
        with patch.object(server.analytics_store, "log_page_view", new=AsyncMock()) as mock_log:
            response = await self.client.post(
                "/api/analytics/pageview",
                json={"session_id": "s1", "url": "https://akaike.lat/", "consent": True},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["accepted"])
            mock_log.assert_awaited_once()

    async def test_event_without_consent_is_not_stored(self):
        with patch.object(server.analytics_store, "log_event", new=AsyncMock()) as mock_log:
            response = await self.client.post(
                "/api/analytics/event",
                json={"session_id": "s1", "event_type": "click", "consent": False},
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["accepted"])
            mock_log.assert_not_awaited()

    async def test_associate_without_consent_is_rejected(self):
        with patch.object(server.signals_association, "record_signals_association", new=AsyncMock()) as mock:
            response = await self.client.post(
                "/api/signals/associate",
                json={
                    "chat_session_id": "chat-1",
                    "signals_visitor_id": "vis-1",
                    "signals_session_id": "ses-1",
                    "consent": False,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["associated"])
            mock.assert_not_awaited()

    async def test_associate_with_consent_is_stored(self):
        with patch.object(server.signals_association, "record_signals_association", new=AsyncMock()) as mock:
            response = await self.client.post(
                "/api/signals/associate",
                json={
                    "chat_session_id": "chat-1",
                    "signals_visitor_id": "vis-1",
                    "signals_session_id": "ses-1",
                    "consent": True,
                    "consent_version": "v1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["associated"])
            mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
