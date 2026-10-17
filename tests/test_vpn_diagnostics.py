"""Tests for VPN evidence collection, comparison and local-only export."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from winnat_ui import vpn_diagnostics as vpn


class VpnDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vpn.json"

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def fake(state, fail=None):
        result = {}
        for name in vpn.SECTIONS:
            if name == fail:
                result[name] = {"ok": False, "rows": [], "error": "Permesso negato"}
            elif name == "interfaces":
                result[name] = {"ok": True, "rows": [
                    {"InterfaceAlias": "Wi-Fi", "Forwarding": state, "InterfaceMetric": 10}]}
            elif name == "nats":
                result[name] = {"ok": True, "rows": ([{"Name": "NAT-Firewall"}] if state == "Enabled" else [])}
            else:
                result[name] = {"ok": True, "rows": []}
        return json.dumps(result)

    def test_dashboard_phase_suggestion_never_asserts_vpn_connected(self):
        self.assertEqual(vpn.suggest_phase({"nats": [{"Name": "NAT-Firewall"}]}, {}), "winnat")
        self.assertEqual(vpn.suggest_phase({"nats": []}, {}), "before")
        self.assertEqual(vpn.suggest_phase({"nats": []}, {"before": {}, "winnat": {}}), "rollback")
        self.assertEqual(vpn.suggest_phase(None, {}), "before")
        self.assertEqual(vpn.suggest_phase({"nats": [{"Name": "Unrelated"}]}, {}), "winnat")

    def test_three_phases_save_without_mutations(self):
        calls = []
        for phase, forwarding in (("before", "Disabled"), ("winnat", "Enabled"),
                                  ("rollback", "Disabled")):
            vpn.capture(phase, lambda script, f=forwarding: (calls.append(script), self.fake(f))[1],
                        path=self.path)
        self.assertEqual(len(calls), 3)
        for script in calls:
            self.assertIn("Get-NetRoute", script)
            self.assertIn("Get-NetIPInterface", script)
            self.assertIn("Get-NetNat", script)
            self.assertNotIn("Set-NetIPInterface", script)
            self.assertNotIn("Remove-NetNat", script)
        recorded = vpn.read(self.path)
        self.assertEqual(set(recorded["snapshots"]), set(vpn.PHASES))
        diff = vpn.comparison(recorded["snapshots"]["before"], recorded["snapshots"]["winnat"])
        self.assertIn("interfaces", diff)
        self.assertIn("nats", diff)
        self.assertEqual(vpn.comparison(recorded["snapshots"]["before"],
                                        recorded["snapshots"]["rollback"]), {})

    def test_partial_command_error_survives(self):
        result = vpn.capture("before", lambda _: self.fake("Disabled", fail="routes"), self.path)
        self.assertFalse(result["sections"]["routes"]["ok"])
        self.assertIn("Permesso", result["sections"]["routes"]["error"])
        self.assertIn("routes", vpn.report(vpn.read(self.path)))

    def test_missing_phases_are_visible_and_export_local(self):
        vpn.capture("before", lambda _: self.fake("Disabled"), self.path)
        data = vpn.read(self.path)
        markdown = vpn.report(data)
        self.assertIn("DA ACQUISIRE", markdown)
        output = Path(self.tmp.name) / "issue-76.md"
        vpn.export(output, data)
        self.assertEqual(output.read_text(encoding="utf-8"), markdown)

    @unittest.skipUnless(sys.platform == "win32", "Richiede PowerShell su Windows")
    def test_windows_powershell_read_only_capture(self):
        """Exercise the actual PowerShell collector on a Windows CI host."""
        snap = vpn.capture("before", path=self.path)
        self.assertTrue(snap["sections"]["interfaces"]["ok"])
        self.assertTrue(snap["sections"]["routes"]["ok"])
        self.assertTrue(self.path.exists())

    def test_invalid_phase_does_not_execute(self):
        with self.assertRaises(ValueError):
            vpn.capture("anything", lambda _: self.fail("should not execute"), self.path)
        self.assertFalse(self.path.exists())

    def test_invalid_read_and_invalid_powershell_json(self):
        with self.assertRaises(ValueError):
            vpn.capture("before", lambda _: "[]", self.path)
        self.path.write_text('{"schema":999,"snapshots":{}}', encoding="utf-8")
        with self.assertRaises(ValueError):
            vpn.read(self.path)


if __name__ == "__main__":
    unittest.main()
