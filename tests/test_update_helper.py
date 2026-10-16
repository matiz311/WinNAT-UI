"""Update helper: no console window, progress window, real PowerShell run on Windows."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from winnat_ui import updater


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
            self.assertIn("Hidden", command)
            self.assertEqual(command[command.index("-ToVersion") + 1], "1.15.0")
            self.assertEqual(command[command.index("-FromVersion") + 1], "1.14.0")
            self.assertNotIn("-NoUi", command)
            # BOM keeps accented text readable for Windows PowerShell 5.1.
            self.assertTrue((stage / "apply-update.ps1").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_script_has_progress_window_and_rollback(self):
        script = updater.HELPER_PS
        for needed in ("System.Windows.Forms", "Copia di sicurezza", "Ripristino",
                       "Get-FileHash", "Disable-Ui"):
            self.assertIn(needed, script)


def _dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


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
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Sta", "-ExecutionPolicy",
             "Bypass", "-File", str(script), "-ParentPid", str(_dead_pid()),
             "-InstallDir", str(inst), "-StageRoot", str(stage),
             "-FromVersion", "1.14.0", "-ToVersion", "1.15.0", "-NoLaunch", *extra],
            capture_output=True, text=True, timeout=180)
        log = (stage / "update-log.txt").read_text(encoding="utf-8-sig")
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

    def test_invalid_package_leaves_installation_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, inst, stage, log = self._run(tmp, "-NoUi", new_exe=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual((inst / "WinNAT-UI.exe").read_text(), "old")
            self.assertIn("Eseguibile nuovo assente", log)


if __name__ == "__main__":
    unittest.main()
