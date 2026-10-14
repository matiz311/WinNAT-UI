"""Privacy regression tests: unknown log content must never enter an issue URL."""
import unittest
from urllib.parse import parse_qs, urlparse

import bug_report


class BugReportTests(unittest.TestCase):
    def test_report_is_allowlisted_and_contains_no_sensitive_inputs(self):
        sensitive = [
            "10.10.10.1", "192.168.1.22", "2001:db8::abcd",
            "AA:BB:CC:DD:EE:FF", "00-15-5d-01-02-03",
            "Connessione di rete Bluetooth", "Loopback0", "HQ-Firewall",
            "C:\\Users\\mario.rossi\\Documents\\private.xml",
            "/home/alice/private/secret.txt",
            "mario.rossi@example.com", "password=superSecret123",
            "token=AbC012secret", "MYPC-CORP", "corp.example.internal",
        ]
        message = ("ESECUZIONE POWERSHELL NON RIUSCITA\nPowerShell exit code: 1\n"
                   "STDERR:\nImpossibile impostare IP statico LAN tramite netsh: "
                   "L'oggetto esiste già.\n" + "\n".join(sensitive)
                   + "\nSCRIPT ESEGUITO:\nNew-NetIPAddress -IPAddress 10.10.10.1")
        trace = ('Traceback (most recent call last):\n'
                 ' File "C:\\Users\\mario.rossi\\AppData\\app.py", line 819, in runner\n'
                 ' File "D:\\project\\network_guide.py", line 147, in execute\n'
                 ' File "/home/alice/private/secret.py", line 1, in secret\n'
                 'RuntimeError: ' + message)
        title, body = bug_report.make_report("Commit", message, trace, "1.9.4")
        url = bug_report.issue_link("Commit", message, trace, "1.9.4")
        self.assertIn("Commit", title)
        self.assertIn("Oggetto Windows già esistente", body)
        self.assertIn("PowerShell:** 1", body)
        self.assertIn("app.py", body)
        self.assertIn("network_guide.py", body)
        self.assertNotIn("secret.py", body)
        for secret in sensitive:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, title + body + url)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["title"], [title])
        self.assertEqual(query["body"], [body])

    def test_never_echoes_unrecognized_error_or_operation(self):
        marker = "TOP_SECRET_INFORMATION_4798"
        title, body = bug_report.make_report(marker, marker, marker, marker)
        self.assertNotIn(marker, title + body)
        self.assertIn("Altra operazione", body)
        self.assertIn("Non determinata", body)

    def test_no_sensitive_data_even_if_in_exception_name_or_module(self):
        message = "Exit code: 55; hostname=OFFICE-BOX; wifi=SSID-Secret"
        trace = ('File "/etc/username/private.py", line 1, in fn\n'
                 'MySensitiveClassError: employee@example.org')
        _, body = bug_report.make_report("Commit", message, trace, "1.9.4")
        self.assertIn("55", body)
        self.assertNotIn("private.py", body)
        self.assertNotIn("MySensitiveClassError", body)
        self.assertNotIn("employee@example.org", body)

    def test_unknown_category_never_contains_raw_text(self):
        message = "Rete di Produzione-OT IP 172.19.17.1 non connessa"
        title, body = bug_report.make_report("Commit", message, "", "1.9.4")
        self.assertIn("Errore operativo non classificato", body)
        self.assertNotIn("Produzione-OT", title + body)
        self.assertNotIn("172.19.17.1", title + body)


if __name__ == "__main__":
    unittest.main()
