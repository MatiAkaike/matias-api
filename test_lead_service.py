import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import lead_service
from agent_prompt import SYSTEM_PROMPT


class LeadExtractionTests(unittest.TestCase):
    def test_extracts_contact_data_from_spanish_text(self):
        text = (
            "Hola, mi nombre es Laura Pérez. Trabajo en Cooperativa Demo. "
            "Mi cargo: gerente de riesgo. Correo laura@example.com y WhatsApp 300 123 4567"
        )
        lead = lead_service._extract_lead_data(text)
        self.assertEqual(lead["nombre"], "Laura Pérez")
        self.assertEqual(lead["empresa"], "Cooperativa Demo")
        self.assertEqual(lead["cargo"], "gerente de riesgo")
        self.assertEqual(lead["correo"], "laura@example.com")
        self.assertEqual(lead["whatsapp"], "3001234567")

    def test_does_not_accept_short_number_as_phone(self):
        lead = lead_service._extract_lead_data("Tenemos 25 solicitudes y 3 productos")
        self.assertNotIn("whatsapp", lead)

    def test_latest_contact_correction_wins(self):
        lead = lead_service._extract_lead_data(
            "Mi correo es anterior@example.com y mi WhatsApp 3001112233. "
            "Corrección: nuevo@example.com y 3014445566"
        )
        self.assertEqual(lead["correo"], "nuevo@example.com")
        self.assertEqual(lead["whatsapp"], "3014445566")


class AgentConfigurationTests(unittest.TestCase):
    def test_prompt_uses_canonical_calendar_and_hides_prices(self):
        self.assertIn("https://calendar.app.google/up2iyv5hJkJpRJta9", SYSTEM_PROMPT)
        self.assertIn("No reveles precios", SYSTEM_PROMPT)

    def test_tracked_runtime_files_do_not_contain_known_secret_defaults(self):
        root = Path(__file__).parent
        server = (root / "server.py").read_text(encoding="utf-8")
        render = (root / "render.yaml").read_text(encoding="utf-8")
        self.assertNotRegex(server, r"TELEGRAM_BOT_TOKEN\s*=\s*os\.getenv\([^\n]+,[^\n]+:[^\n]+\)")
        self.assertIn("SUPABASE_PASSWORD\n        sync: false", render)


class LeadPersistenceSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_fails_when_session_ids_are_duplicated(self):
        conn = AsyncMock()
        conn.fetchval.return_value = 2

        class Acquire:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_args):
                return False

        pool = Mock()
        pool.acquire.return_value = Acquire()
        with patch.object(lead_service.database, "_get_pg_pool", AsyncMock(return_value=pool)):
            with self.assertRaisesRegex(RuntimeError, "session_id duplicados"):
                await lead_service.init_leads_db()

        unique_index_calls = [
            call for call in conn.execute.await_args_list
            if "uq_leads_session_id" in str(call)
        ]
        self.assertEqual(unique_index_calls, [])

    def test_claims_use_independent_channel_timestamps(self):
        source = Path(lead_service.__file__).read_text(encoding="utf-8")
        for channel in ("email", "whatsapp", "telegram"):
            self.assertIn(f"{channel}_claimed_at < NOW()", source)
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {channel}_claimed_at", source)
        self.assertIn('f"{channel}_claimed_at=NULL', source)


if __name__ == "__main__":
    unittest.main()
