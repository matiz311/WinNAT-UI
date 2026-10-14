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

    def test_network_command_logger_is_scoped(self):
        from unittest.mock import patch
        import network
        from types import SimpleNamespace
        events = []
        process = SimpleNamespace(returncode=0, stdout="OK\n", stderr="")
        with patch("network.subprocess.run", return_value=process):
            token = network.command_logger.set(lambda kind, value: events.append((kind, value)))
            try:
                self.assertEqual(network.ps("Write-Output 'OK'"), "OK")
            finally:
                network.command_logger.reset(token)
        self.assertEqual([name for name, _ in events], ["command", "stdout", "status"])
        self.assertIn("Write-Output", events[0][1])

    def test_network_command_logger_captures_stderr_before_raising(self):
        from unittest.mock import patch
        import network
        from types import SimpleNamespace
        events = []
        process = SimpleNamespace(returncode=1, stdout="partial", stderr="failed")
        with patch("network.subprocess.run", return_value=process):
            token = network.command_logger.set(lambda kind, value: events.append((kind, value)))
            try:
                with self.assertRaises(RuntimeError):
                    network.ps("throw 'failed'")
            finally:
                network.command_logger.reset(token)
        self.assertEqual([name for name, _ in events], ["command", "stdout", "stderr", "status"])
        self.assertEqual(events[2][1], "failed")

    def test_reporting_error_does_not_open_another_bug_dialog(self):
        from pathlib import Path
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        start = source.index("    def drain(self):")
        segment = source[start:start + 2500]
        self.assertIn('elif key == "Segnala bug":', segment)
        self.assertIn('"Segnalazione non inviata"', segment)
        self.assertIn('self.show_error_dialog("Operazione non riuscita"', segment)

    def test_original_error_dialog_survives_failed_submission(self):
        from pathlib import Path
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        start = source.index("        def report_bug():")
        end = source.index("        dlg.cancel_btn.configure(command=copy_anonymized)", start)
        body = source[start:end]
        self.assertIn('self.run_task("Segnala bug", send, sent)', body)
        self.assertIn('            def sent(result):\n                dlg.destroy()', body)
        self.assertNotIn('            dlg.destroy()\n            self.run_task(', body)

    def test_bug_submission_does_not_depend_on_public_issue_lookup(self):
        from pathlib import Path
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        begin = source.index("        def report_bug():")
        end = source.index("        dlg.cancel_btn.configure(command=copy_anonymized)", begin)
        segment = source[begin:end]
        self.assertIn("issue_tracker.submit(payload, endpoint=endpoint)", segment)
        self.assertNotIn("issue_tracker.public_issues()", segment)

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
