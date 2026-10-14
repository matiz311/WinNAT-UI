"""Tests for pure UI helpers (no window is created)."""
import unittest
import app


class HelperTests(unittest.TestCase):
    def test_on_off_values_from_powershell(self):
        for value in (1, "1", True, "Enabled"):
            self.assertTrue(app.is_on(value))
        for value in (0, "0", False, "Disabled", None):
            self.assertFalse(app.is_on(value))
        self.assertEqual(app.yes_no(None), "—")

    def test_friendly_ip_errors(self):
        import ipaddress
        try:
            ipaddress.IPv4Network("10.10.10.5/24")
        except ValueError as exc:
            self.assertIn("indirizzo di rete", app.friendly_ip_error(exc, "10.10.10.0/24"))
        try:
            ipaddress.IPv4Network("10.10.300.0/24")
        except ValueError as exc:
            self.assertIn("Formato non valido", app.friendly_ip_error(exc, "10.10.10.0/24"))

    def test_service_status(self):
        self.assertEqual(app.service_status(4), "In esecuzione")
        self.assertEqual(app.service_status("Stopped"), "Arrestato")


if __name__ == "__main__":
    unittest.main()
