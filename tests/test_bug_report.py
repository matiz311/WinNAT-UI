"""Regression tests for detailed diagnostics and targeted credential masking."""
import unittest
from urllib.parse import parse_qs, urlparse

from winnat_ui import bug_report


class BugReportTests(unittest.TestCase):
    def test_report_preserves_relevant_command_output_and_network_context(self):
        message = (
            "ESECUZIONE POWERSHELL NON RIUSCITA\nExit code: 1\n"
            "STDERR:\nNew-NetIPAddress : L'oggetto esiste già.\n"
            "STDOUT:\nTentativo con interfaccia Ethernet 2\n"
            "SCRIPT ESEGUITO:\nNew-NetIPAddress -IPAddress 10.10.10.1 -PrefixLength 24\n"
            "password=superSecret123\n"
            "token=AbC012secret\n"
            "C:\\Users\\mario.rossi\\AppData\\Local\\config.txt\n"
            "mario.rossi@example.com\n"
        )
        trace = (
            'Traceback (most recent call last):\n'
            '  File "C:\\Users\\mario.rossi\\AppData\\app.py", line 819, in runner\n'
            '  File "D:\\project\\network_guide.py", line 147, in execute\n'
            "RuntimeError: " + message
        )
        inventory = {
            "adapters": [{"Name": "Ethernet 2", "Status": "Up"}],
            "ips": [{"InterfaceAlias": "Ethernet 2", "IPAddress": "10.10.10.1", "PrefixLength": 24}],
            "nats": [{"Name": "NAT-LAN", "InternalIPInterfaceAddressPrefix": "10.10.10.0/24"}],
        }
        payload = bug_report.build_payload("Commit", message, trace, "1.14.0", inventory, True)
        title, body = bug_report.format_report(payload)
        self.assertIn("New-NetIPAddress", body)
        self.assertIn("Ethernet 2", body)
        self.assertIn("10.10.10.1", body)
        self.assertIn("10.10.10.0/24", body)
        self.assertIn("RuntimeError", body)
        self.assertIn("app.py", body)
        self.assertIn("network_guide.py", body)
        self.assertIn("1.14.0", body)
        self.assertIn("New-NetIPAddress", title)
        self.assertIn("ESECUZIONE POWERSHELL", body)
        for secret in ["superSecret123", "AbC012secret", "mario.rossi@example.com", r"Users\mario.rossi"]:
            self.assertNotIn(secret, title + body)
        self.assertEqual(len(payload["signature"]), 24)

    def test_unknown_errors_are_preserved_instead_of_suppressed(self):
        unknown = "Errore custom su rete Produzione-OT IP 172.19.17.1"
        title, body = bug_report.make_report("Commit", unknown, "", "1.14.0.1")
        self.assertIn(unknown, body)
        self.assertIn("172.19.17.1", body)
        self.assertIn("Errore operativo non classificato", title)
        self.assertIn("1.14.0.1", body)

    def test_sensitive_patterns_are_redacted_without_discarding_diagnostics(self):
        text = (
            "Authorization: Bearer AbcDef01234567890\n"
            "password='my secret pass'\n"
            "https://user:pass@host.example.net/a\n"
            "C:\\Users\\alice\\Desktop\\file.txt\n"
            "New-NetNat -Name Office -InternalIPInterfaceAddressPrefix 192.168.55.0/24"
        )
        safe = bug_report.redact(text)
        for secret in ["AbcDef01234567890", "my secret pass", "user:pass", r"Users\alice"]:
            self.assertNotIn(secret, safe)
        self.assertIn("New-NetNat", safe)
        self.assertIn("192.168.55.0/24", safe)

    def test_large_sections_are_bounded_with_truncation_marker(self):
        payload = bug_report.build_payload("Commit", "X" * 50000, "Y" * 40000, "1.14.0")
        self.assertLessEqual(len(payload["message"]), 16000)
        self.assertLessEqual(len(payload["traceback"]), 13000)
        self.assertIn("TRONCATO", payload["message"])
        self.assertIn("TRONCATO", payload["traceback"])

    def test_manual_link_does_not_generate_excessive_url(self):
        url = bug_report.issue_link("Commit", "failure " + "X" * 30000, "", "1.14.0")
        self.assertTrue(len(url) < 7000)
        query = parse_qs(urlparse(url).query)
        self.assertTrue(query["title"][0].startswith("[Bug]"))


if __name__ == "__main__":
    unittest.main()
