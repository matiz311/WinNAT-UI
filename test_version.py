"""Versioning must stay consistent across app, Windows metadata and changelog."""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import release  # noqa: E402
from version import VERSION  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_semver(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+(?:\.\d+)?$")

    def test_windows_metadata_matches(self):
        text = (ROOT / "version_info.txt").read_text(encoding="utf-8")
        parts = [int(x) for x in VERSION.split(".")]
        tup = "(" + ", ".join(map(str, parts + [0] * (4 - len(parts)))) + ")"
        self.assertIn("filevers=" + tup, text)
        self.assertIn("prodvers=" + tup, text)
        self.assertEqual(re.findall(r"'(?:FileVersion|ProductVersion)', '([^']*)'", text), [VERSION if VERSION.count(".") == 3 else VERSION + ".0"] * 2)

    def test_changelog_has_section(self):
        self.assertTrue(release.notes(VERSION))

    def test_app_uses_single_source(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("from version import VERSION", app)
        self.assertNotRegex(app, r'VERSION\s*=\s*"')
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertNotRegex(workflow, r"v\d+\.\d+\.\d+", "il workflow non deve contenere versioni fisse")

    def test_no_conflict_markers(self):
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file() or path.suffix not in {".py", ".yml", ".md", ".txt", ".ps1"}:
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                self.assertFalse(line.startswith(("<<<<<<< ", ">>>>>>> ")) or line == "=======",
                                 "marker di conflitto in " + str(path))


if __name__ == "__main__":
    unittest.main()
