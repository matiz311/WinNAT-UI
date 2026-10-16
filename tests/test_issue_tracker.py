"""Privacy, deduplication, offline behavior and resolved-release tracking tests."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlparse
from winnat_ui import issue_tracker as it


class IssueTrackerTests(TestCase):
    def test_payload_retains_diagnostics_and_masks_explicit_secrets(self):
        confidential = "192.168.12.5 PASSWORD=verySensitive C:\\Users\\company\\secret.xml"
        error = "Access is denied Exit code: 5 " + confidential
        stack = 'File "C:\\Users\\company\\app.py", line 20, in execute\nRuntimeError: ' + confidential
        payload = it.safe_payload("Commit", error, stack, "1.9.5")
        self.assertTrue({"operation", "category", "exception", "modules", "version", "exit_code",
                         "signature", "summary", "message", "traceback", "environment",
                         "inventory"}.issubset(payload))
        self.assertEqual(payload["exit_code"], 5)
        self.assertEqual(payload["category"], "Accesso negato")
        self.assertIn("192.168.12.5", json.dumps(payload))
        self.assertNotIn("verySensitive", json.dumps(payload))
        self.assertNotIn(r"Users\company", json.dumps(payload))


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

    def test_public_issues_reads_renamed_title_triage_and_pagination(self):
        signature = "a" * 24
        item = {"number": 65, "html_url": "https://github.com/matiz311/WinNAT-UI/issues/65",
                "state": "open", "title": "Errore DNS durante verifica stato",
                "body": "<!-- winnat-fingerprint:" + signature + " -->",
                "updated_at": "2026-10-16T20:00:00Z",
                "labels": [{"name": "bug-report"}, {"name": "triage:in-analisi"},
                           {"name": "priority:high"}, {"name": "fixed-in/v1.16.0"}]}
        with patch("winnat_ui.issue_tracker._read_json", return_value=[item]) as get:
            issues = it.public_issues()
        self.assertEqual(get.call_count, 1)
        self.assertEqual(issues[signature][0]["title"], item["title"])
        self.assertEqual(issues[signature][0]["triage"], "in-analisi")
        self.assertEqual(issues[signature][0]["priority"], "high")
        self.assertEqual(issues[signature][0]["fixed_in"], "1.16.0")

    def test_fixed_in_hotfix_label_is_recognized(self):
        signature = "b" * 24
        item = {"number": 44, "html_url": "https://github.com/matiz311/WinNAT-UI/issues/44",
                "state": "closed", "title": "Updater - release assente",
                "body": "<!-- winnat-fingerprint:" + signature + " -->",
                "labels": [{"name": "bug-report"},
                           {"name": "fixed-in/v1.15.0.1"}]}
        with patch("winnat_ui.issue_tracker._read_json", return_value=[item]):
            issue = it.public_issues()[signature][0]
        self.assertEqual(issue["fixed_in"], "1.15.0.1")

    def test_sync_updates_title_but_preserves_original_issue_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "issues.json"
            payload = it.safe_payload("Commit", "Access denied", "", "1.9.5")
            issue = {"number": 42, "url": "https://github.com/matiz311/WinNAT-UI/issues/42"}
            with patch("winnat_ui.issue_tracker.store_path", return_value=path):
                original = it.save_entry(payload, issue)
                matched = dict(number=42, state="open", fixed_in=None,
                               title="LAN — Indirizzo IPv4 non applicato",
                               triage="confermato", priority="high",
                               updated_at="2026-10-16T20:00:00Z")
                entries, _ = it.synchronize(remote={original["fingerprint"]: [matched]})
                self.assertEqual(entries[0]["number"], 42)
                self.assertEqual(entries[0]["title"], matched["title"])
                self.assertEqual(entries[0]["triage"], "confermato")
                self.assertEqual(entries[0]["priority"], "high")
                self.assertEqual(entries[0]["updated_at"], matched["updated_at"])

    def test_similar_issue_by_signature(self):
        p = it.safe_payload("Commit", "Access denied", "", "1.9.5")
        issues = {it.fingerprint(p): [{"number": 7, "state": "open", "url": "https://github.com/matiz311/WinNAT-UI/issues/7"}]}
        self.assertEqual(it.find_similar(p, issues)[0]["number"], 7)


if __name__ == "__main__":
    import unittest
    unittest.main()
