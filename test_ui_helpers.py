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

    def test_debug_retains_multiline_output(self):
        message = "PowerShell exit code: 1\n\nSTDERR:\nErrore di rete\n\nSTDOUT:\nL'oggetto esiste già."
        trace = 'Traceback (most recent call last):\n  File "app.py", line 50'
        formatted = app.format_error_debug("Commit", message, trace)
        self.assertIn("Operazione: Commit", formatted)
        self.assertIn("STDERR:\nErrore di rete", formatted)
        self.assertIn("STDOUT:\nL'oggetto esiste già.", formatted)
        self.assertIn("Traceback (most recent call last):", formatted)

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

    def test_error_summary_skips_exit_code(self):
        message = ("PowerShell exit code: 1\n\nSTDERR:\nNew-NetIPAddress : Inconsistent parameters "
                   "PolicyStore PersistentStore and Dhcp Enabled\nIn riga:12 car:1")
        self.assertTrue(app.error_summary(message).startswith("New-NetIPAddress : Inconsistent"))
        self.assertIn("sconosciuto", app.error_summary("PowerShell exit code: 1\n\nSTDERR:"))
        self.assertEqual(app.error_summary("Errore semplice"), "Errore semplice")
        detailed = ("ESECUZIONE POWERSHELL NON RIUSCITA\n\nExit code: 1\n\nInterprete: powershell.exe\n\n"
                    "STDERR (integrale):\nnetsh : L'oggetto esiste gi\u00e0.\nIn riga:7 car:1\n\n"
                    "STDOUT (integrale):\n(vuoto)")
        self.assertEqual(app.error_summary(detailed), "netsh : L'oggetto esiste gi\u00e0.")

    def test_service_status(self):
        self.assertEqual(app.service_status(4), "In esecuzione")
        self.assertEqual(app.service_status("Stopped"), "Arrestato")

    def test_icon_assets(self):
        import os
        import struct
        ico = app.resource_path("assets", "winnat-ui.ico")
        with open(ico, "rb") as f:
            reserved, kind, count = struct.unpack("<HHH", f.read(6))
            sizes = {(struct.unpack("<BB", f.read(16)[:2])) for _ in range(count)}
        self.assertEqual((reserved, kind), (0, 1))
        for s in (16, 32, 48):
            self.assertIn((s, s), sizes)
        self.assertIn((0, 0), sizes)   # 256 px is stored as 0 in the ICO directory
        for name in ("winnat-ui-256.png", "winnat-ui-32.png"):
            with open(app.resource_path("assets", name), "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertTrue(os.path.exists(app.resource_path("assets", "winnat-ui.svg")))


if __name__ == "__main__":
    unittest.main()
