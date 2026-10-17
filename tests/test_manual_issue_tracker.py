"""Manual reporting and follow-up without a Python exception."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from winnat_ui import issue_tracker as tracker


class ManualIssueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "reported-issues.json"
        self.patcher = mock.patch.object(tracker, "store_path", return_value=self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    @staticmethod
    def remote(number=76, title="VPN non si collega", state="open"):
        return {
            "number": number, "title": title, "state": state,
            "updated_at": "2026-10-17T18:00:00Z",
            "labels": [{"name": "priority:P2"}, {"name": "triage:in-analisi"}]
        }

    def test_manual_payload_does_not_require_exception(self):
        with mock.patch.object(tracker, "submit", return_value={
            "number": 25, "url": "https://github.com/matiz311/WinNAT-UI/issues/25",
            "already_exists": False}) as submit:
            result = tracker.submit_manual(
                "Richiesta diagnostica", "Report manuale utile",
                "Problema esterno", endpoint="https://example.workers.dev/report")
        self.assertEqual(result["number"], 25)
        data = submit.call_args.args[0]
        self.assertEqual(data["mode"], "manual")
        self.assertIsNone(data["issue_number"])
        self.assertEqual(data["body"], "Report manuale utile")

    def test_explicit_issue_and_invalid_targets(self):
        with mock.patch.object(tracker, "submit", return_value={
            "number": 76, "url": "https://github.com/matiz311/WinNAT-UI/issues/76",
            "already_exists": True}) as submit:
            tracker.submit_manual("Nuova evidenza", "Dettaglio", "Problema esterno", 76)
            self.assertEqual(submit.call_args.args[0]["issue_number"], 76)
        for target in ("76", -1, True, 100000000, 0):
            with self.assertRaises(ValueError):
                tracker.submit_manual("Nuova evidenza", "Dettaglio",
                                      "Problema esterno", target)

    def test_track_external_issue_and_refresh_without_fingerprint_marker(self):
        with mock.patch.object(tracker, "_read_json", return_value=self.remote()):
            value = tracker.track_issue(76)
        self.assertEqual(value["triage"], "in-analisi")
        history = tracker.history()
        self.assertTrue(history[0]["manually_added"])
        self.assertEqual(history[0]["number"], 76)
        with mock.patch.object(tracker, "_read_json",
                               return_value=self.remote(state="closed",title="Titolo aggiornato")):
            entries, _ = tracker.synchronize(remote={})
        self.assertEqual(entries[0]["state"], "closed")
        self.assertEqual(entries[0]["title"], "Titolo aggiornato")
        self.assertEqual(entries[0]["priority"], "P2")
        self.assertEqual(entries[0]["triage"], "in-analisi")

    def test_import_rejects_pull_requests(self):
        with mock.patch.object(tracker, "_read_json",
                               return_value={**self.remote(), "pull_request": {}}):
            with self.assertRaises(ValueError):
                tracker.track_issue(76)

    def test_save_manual_entry_preserves_existing_report_without_duplicate(self):
        issue = {"number": 76, "url": "https://github.com/matiz311/WinNAT-UI/issues/76",
                 "already_exists": True}
        tracker.save_manual_entry("Nuovo", "Problema esterno", issue)
        tracker.save_manual_entry("Nuovo", "Problema esterno", issue)
        self.assertEqual(len(tracker.history()), 1)


if __name__ == "__main__":
    unittest.main()
