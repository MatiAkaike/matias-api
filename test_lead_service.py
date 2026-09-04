import unittest
from pathlib import Path

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
        self.assertIn("https://calendar.app.google/YhY1KSgjktrRrcBb6", SYSTEM_PROMPT)
        self.assertIn("No reveles precios", SYSTEM_PROMPT)

    def test_tracked_runtime_files_do_not_contain_known_secret_defaults(self):
        root = Path(__file__).parent
        server = (root / "server.py").read_text(encoding="utf-8")
        render = (root / "render.yaml").read_text(encoding="utf-8")
        self.assertNotRegex(server, r"TELEGRAM_BOT_TOKEN\s*=\s*os\.getenv\([^\n]+,[^\n]+:[^\n]+\)")
        self.assertIn("SUPABASE_PASSWORD\n        sync: false", render)


if __name__ == "__main__":
    unittest.main()
