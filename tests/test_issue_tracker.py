"""Privacy, deduplication, offline behavior and resolved-release tracking tests."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlparse
from winnat_ui import issue_tracker as it


class IssueTrackerTests(TestCase):
    def test_payload_contains_only_allowlisted_values(self):
        confidential = "192.168.12.5 PASSWORD=verySensitive C:\\Users\\company\\secret.xml"
        error = "Access is denied Exit code: 5 " + confidential
        stack = 'File "C:\\Users\\company\\app.py", line 20, in execute\nRuntimeError: ' + confidential
        payload = it.safe_payload("Commit", error, stack, "1.9.5")
        self.assertEqual(set(payload), {"operation", "category", "exception", "modules", "version", "exit_code"})
        self.assertEqual(payload["exit_code"], 5)
        self.assertEqual(payload["category"], "Accesso negato")
        self.assertNotIn(confidential, json.dumps(payload))
        self.assertNotIn("192.168.", json.dumps(payload))

    def test_same_problem_across_versions_has_same_signature(self):
        payload = it.safe_payload("Commit", "Access denied", "RuntimeError: problem", "1.9.5")
        changed = dict(payload, version="1.9.10", exit_code=99)
        self.assertEqual(it.fingerprint(payload), it.fingerprint(changed))

    def test_different_problem_different_fingerprint(self):
        original = it.safe_payload("Commit", "Access denied", "", "1.9.5")
        another = dict(original, category="Ripristino non completato")
        self.assertNotEqual(it.fingerprint(original), it.fingerprint(another))

    def test_unconfigured_backend_does_not_contact_github_with_secret(self):
        with patch("winnat_ui.issue_tracker.service_endpoint", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "non ancora configurato"):
                it.submit(it.safe_payload("Commit", "Access denied", "", "1.9.5"))

    def test_unsafe_endpoint_rejected(self):
        for endpoint in ("http://evil.workers.dev/report",
                         "https://attacker.com/report",
                         "https://someone.workers.dev@evil.com/report"):
            with self.subTest(endpoint=endpoint):
                with patch("winnat_ui.issue_tracker._read_json", return_value={"submit_url": endpoint}):
                    self.assertIsNone(it.service_endpoint())

    def test_save_then_sync_issue_fixed_only_in_published_new_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            payload = it.safe_payload("Commit", "Access denied", "", "1.9.5")
            issue = {"number": 42, "url": "https://github.com/matiz311/WinNAT-UI/issues/42"}
            with patch("winnat_ui.issue_tracker.store_path", return_value=path):
                item = it.save_entry(payload, issue)
                found = {it.fingerprint(payload): [{"number": 42, "state": "closed",
                    "fixed_in": "1.9.8", "fingerprint": it.fingerprint(payload)}]}
                entries, _ = it.synchronize(installed="1.9.5", remote=found, latest_version="1.9.7")
                self.assertFalse(entries[0]["fix_available"])
                entries, _ = it.synchronize(installed="1.9.5", remote=found, latest_version="1.9.8")
                self.assertTrue(entries[0]["fix_available"])
                entries, _ = it.synchronize(installed="1.9.8", remote=found, latest_version="1.9.8")
                self.assertFalse(entries[0]["fix_available"])
                self.assertEqual(entries[0]["number"], 42)

    def test_similar_issue_by_signature(self):
        p = it.safe_payload("Commit", "Access denied", "", "1.9.5")
        issues = {it.fingerprint(p): [{"number": 7, "state": "open", "url": "https://github.com/matiz311/WinNAT-UI/issues/7"}]}
        self.assertEqual(it.find_similar(p, issues)[0]["number"], 7)


if __name__ == "__main__":
    import unittest
    unittest.main()
