"""Update helper: no console window, progress window, real PowerShell run on Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from winnat_ui import bug_report, updater


class LaunchTests(unittest.TestCase):
    def test_helper_runs_without_console_and_with_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            (stage / "new").mkdir(parents=True)
            (stage / "new" / "WinNAT-UI.exe").write_bytes(b"new")
            install = Path(tmp) / "inst"
            install.mkdir()
            with patch.object(updater.sys, "platform", "win32"), \
                    patch.object(updater.sys, "frozen", True, create=True), \
                    patch("winnat_ui.updater.subprocess.Popen") as popen:
                updater.launch(stage, install_dir=install, parent_pid=1234,
                               from_version="1.14.0", to_version="1.15.0")
            args, kwargs = popen.call_args
            command = args[0]
            self.assertTrue(kwargs["creationflags"] & updater.CREATE_NO_WINDOW)
            # No -WindowStyle Hidden: it could hide the progress window itself.
            self.assertNotIn("Hidden", command)
            self.assertEqual(command[command.index("-ToVersion") + 1], "1.15.0")
            self.assertEqual(command[command.index("-FromVersion") + 1], "1.14.0")
            self.assertNotIn("-NoUi", command)
            self.assertNotIn("PSModulePath", {k for k in kwargs["env"]})
            # BOM keeps accented text readable for Windows PowerShell 5.1.
            self.assertTrue((stage / "apply-update.ps1").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_script_has_progress_window_and_rollback(self):
        script = updater.HELPER_PS
        for needed in ("System.Windows.Forms", "Copia di sicurezza", "Ripristino",
                       "Get-Sha256", "Disable-Ui"):
            self.assertIn(needed, script)


class FailureReportTests(unittest.TestCase):
    FAILURE = {"schema": 1, "from_version": "1.14.0", "to_version": "1.15.0",
               "step": "Installazione della nuova versione",
               "error": "Access to the path 'C:\\Users\\mario\\x.dll' is denied.",
               "outcome": "La versione precedente è stata ripristinata.",
               "exit_code": 1, "time": "2026-10-16T19:00:00Z",
               "log": "2026-10-16  Fase: Installazione della nuova versione"}

    def _write(self, tmp, data):
        path = Path(tmp) / updater.FAILURE_FILE
        raw = data if isinstance(data, str) else json.dumps(data)
        path.write_text(raw, encoding="utf-8-sig")
        return path

    def test_valid_failure_is_read_and_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, self.FAILURE)
            failure = updater.pending_failure(path)
            self.assertEqual(failure["step"], "Installazione della nuova versione")
            updater.clear_failure(path)
            self.assertFalse(path.exists())
            updater.clear_failure(path)  # already gone: no error

    def test_invalid_failure_files_are_ignored(self):
        bad = ["{not json", json.dumps([1]), json.dumps(dict(self.FAILURE, schema=2)),
               json.dumps(dict(self.FAILURE, error=7)), json.dumps(dict(self.FAILURE, error=" ")),
               json.dumps(dict(self.FAILURE, log="x" * (updater.MAX_FAILURE_BYTES + 1)))]
        with tempfile.TemporaryDirectory() as tmp:
            for raw in bad:
                with self.subTest(raw=raw[:30]):
                    self.assertIsNone(updater.pending_failure(self._write(tmp, raw)))
            self.assertIsNone(updater.pending_failure(Path(tmp) / "missing.json"))

    def test_report_payload_fits_gateway_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            failure = updater.pending_failure(self._write(tmp, self.FAILURE))
        message = updater.failure_message(failure)
        self.assertTrue(message.startswith("Access to the path"))
        payload = bug_report.build_payload("Aggiornamento", message, "", "1.14.0")
        # Same constraints as services/bug-gateway/src/index.js.
        categories = {label for _p, label in bug_report.KNOWN_ERRORS} | {"Errore operativo non classificato"}
        self.assertIn(payload["category"], categories)
        self.assertEqual(payload["exception"], "Non determinato")
        self.assertRegex(payload["operation"], r"^[\w ./:+()\-]{1,80}$")
        self.assertEqual(payload["exit_code"], 1)
        self.assertTrue(payload["summary"].startswith("Access to the path"))
        self.assertNotIn("mario", payload["message"])  # username in the path is redacted
        self.assertIn("non disponibile", payload["inventory"])


# Windows PIDs are multiples of 4 well below this value, so it never belongs to
# a live process (a recycled PID would make the helper wait for 45 s).
ABSENT_PID = 2147483644


@unittest.skipUnless(sys.platform == "win32", "richiede Windows")
class HelperOnWindowsTests(unittest.TestCase):
    def _run(self, tmp, *extra, new_exe=True):
        root = Path(tmp)
        inst, stage = root / "inst", root / "stage"
        (inst / "_internal").mkdir(parents=True)
        (stage / "new" / "_internal").mkdir(parents=True)
        (inst / "WinNAT-UI.exe").write_text("old")
        (inst / "_internal" / "a.dll").write_text("old")
        (inst / "user.cfg").write_text("keep")
        if new_exe:
            (stage / "new" / "WinNAT-UI.exe").write_text("new")
        (stage / "new" / "_internal" / "a.dll").write_text("new")
        script = stage / "apply-update.ps1"
        script.write_text(updater.HELPER_PS, encoding="utf-8-sig")
        # Same environment as the app (launch() drops PSModulePath): the CI step
        # runs in pwsh 7, whose module path breaks Windows PowerShell 5.1.
        env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Sta", "-ExecutionPolicy",
             "Bypass", "-File", str(script), "-ParentPid", str(ABSENT_PID),
             "-InstallDir", str(inst), "-StageRoot", str(stage),
             "-FromVersion", "1.14.0", "-ToVersion", "1.15.0", "-NoLaunch",
             "-AutoCloseSeconds", "20", "-ReportDir", str(root / "report"), *extra],
            capture_output=True, text=True, timeout=150, env=env)
        log = (stage / "update-log.txt").read_text(encoding="utf-8-sig")
        self.report = root / "report" / updater.FAILURE_FILE
        return result, inst, stage, log

    def test_script_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.ps1"
            path.write_text(updater.HELPER_PS, encoding="utf-8-sig")
            check = ("$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
                     "'" + str(path) + "',[ref]$null,[ref]$e) | Out-Null; $e.Count")
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", check],
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.stdout.strip(), "0", out.stdout + out.stderr)

    def test_update_with_progress_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, inst, stage, log = self._run(tmp)
            self.assertEqual(result.returncode, 0, log + result.stderr)
            self.assertEqual((inst / "WinNAT-UI.exe").read_text(), "new")
            self.assertEqual((inst / "user.cfg").read_text(), "keep")
            self.assertEqual((stage / "previous" / "WinNAT-UI.exe").read_text(), "old")
            self.assertIn("Aggiornamento completato", log)
            # The window may be unavailable on a headless runner, but if it was
            # created no UI call may have failed during the update.
            self.assertNotIn("UI disattivata", log)
            self.assertFalse(self.report.exists())

    def test_invalid_package_leaves_installation_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, inst, stage, log = self._run(tmp, "-NoUi", new_exe=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual((inst / "WinNAT-UI.exe").read_text(), "old")
            self.assertIn("Eseguibile nuovo assente", log)
            failure = updater.pending_failure(self.report)
            self.assertIsNotNone(failure)
            self.assertEqual(failure["error"], "Eseguibile nuovo assente.")
            self.assertEqual(failure["to_version"], "1.15.0")
            self.assertEqual(failure["exit_code"], 1)
            self.assertIn("Fase: Chiusura di WinNAT UI", failure["log"])


if __name__ == "__main__":
    unittest.main()
