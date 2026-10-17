"""Generic diagnostics: capture is opt-in, bounded, and non-mutating."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from winnat_ui import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "diagnostics.json"

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def fake(metric=10, fail=None):
        return json.dumps({
            key: ({"ok": False, "rows": [], "error": "Accesso negato"}
                  if key == fail else
                  {"ok": True, "rows": [{"InterfaceAlias": "Wi-Fi", "InterfaceMetric": metric}]
                   if key == "interfaces" else []})
            for key in diagnostics.SECTIONS
        })

    def test_captures_arbitrary_labels_without_writes_to_network(self):
        seen = []
        for name, metric in (("iniziale", 10), ("problema", 20)):
            diagnostics.capture(name, runner=lambda script, m=metric:
                                (seen.append(script), self.fake(m))[1], path=self.path)
        self.assertEqual(len(seen), 2)
        for script in seen:
            self.assertIn("Get-NetAdapter", script)
            self.assertIn("Get-NetRoute", script)
            self.assertIn("Get-NetNat", script)
            self.assertNotIn("Set-NetIPInterface", script)
            self.assertNotIn("Remove-NetNat", script)
        obj = diagnostics.read(self.path)
        self.assertEqual([x["label"] for x in obj["snapshots"]], ["iniziale", "problema"])
        diff = diagnostics.comparison(*obj["snapshots"])
        self.assertIn("interfaces", diff)

    def test_handles_partial_failure_and_limits_history(self):
        for i in range(9):
            diagnostics.capture("test " + str(i), lambda _: self.fake(i, fail="routes"), path=self.path)
        obj = diagnostics.read(self.path)
        self.assertEqual(len(obj["snapshots"]), diagnostics.MAX_SNAPSHOTS)
        self.assertEqual(obj["snapshots"][0]["label"], "test 3")
        self.assertIn("routes", diagnostics.comparison(*obj["snapshots"][-2:]))

    def test_report_can_exist_without_captures_or_error(self):
        text = diagnostics.build_report("Richiesta generica", "Vorrei una nuova funzione.",
                                        "Miglioramento", data={"snapshots": []}, version="1.16.0")
        self.assertIn("Richiesta generica", text)
        self.assertIn("Snapshot disponibili: 0", text)
        self.assertIn("1.16.0", text)

    def test_report_contains_latest_state_and_difference(self):
        a = diagnostics.capture("prima", lambda _: self.fake(10), self.path)
        b = diagnostics.capture("dopo", lambda _: self.fake(20), self.path)
        report = diagnostics.build_report("Metrica cambiata", "Prima e dopo.",
                                          "Problema esterno", diagnostics.read(self.path))
        self.assertIn("Differenze rispetto al precedente", report)
        self.assertIn("InterfaceMetric", report)
        self.assertNotEqual(a["id"], b["id"])

    def test_reject_bad_capture(self):
        for name in ("", "a\nb", "x" * 81):
            with self.assertRaises(ValueError):
                diagnostics.capture(name, lambda _: self.fake(), self.path)
        with self.assertRaises(ValueError):
            diagnostics.capture("test", lambda _: "[]", self.path)
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(sys.platform == "win32", "Richiede PowerShell Windows")
    def test_real_windows_collector(self):
        snap = diagnostics.capture("Windows CI", path=self.path)
        self.assertTrue(snap["sections"]["interfaces"]["ok"])
        self.assertTrue(snap["sections"]["routes"]["ok"])


if __name__ == "__main__":
    unittest.main()
