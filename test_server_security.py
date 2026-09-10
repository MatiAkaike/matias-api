import unittest
from unittest.mock import patch

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

    def test_request_models_reject_oversized_fields(self):
        with self.assertRaises(ValidationError):
            server.ChatRequest(message="x" * 4001)
        with self.assertRaises(ValidationError):
            server.AnalyticsEvent(
                session_id="session",
                event_type="click",
                metadata="x" * 4001,
            )


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


if __name__ == "__main__":
    unittest.main()
