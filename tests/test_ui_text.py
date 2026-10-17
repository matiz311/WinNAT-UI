"""Static checks on user-facing strings (no window or tkinter needed)."""
import ast
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"


class UiTextTests(unittest.TestCase):
    def test_no_escaped_newlines_in_ui_strings(self):
        """A literal backslash-n would appear as "\\n" in a window instead of a line break."""
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        offenders = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "\\n" in node.value
        ]
        self.assertEqual(offenders, [], "escaped \\n in app.py at lines %s" % offenders)

    def test_vpn_diagnostics_shortcut_visible_and_about_scrollable(self):
        """The reported support button must be on the dashboard and in reachable Information."""
        tree = ast.parse(APP.read_text(encoding="utf-8"))
        methods = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("build_dashboard", methods)
        self.assertIn("build_about", methods)
        self.assertIn("capture_vpn_from_dashboard", methods)
        dashboard_text = ast.get_source_segment(APP.read_text(encoding="utf-8"),
                                               methods["build_dashboard"])
        about_text = ast.get_source_segment(APP.read_text(encoding="utf-8"),
                                           methods["build_about"])
        self.assertIn('text="Raccogli diagnostica VPN"', dashboard_text)
        self.assertIn("command=self.capture_vpn_from_dashboard", dashboard_text)
        self.assertIn("ui.ScrollFrame(page)", about_text)
        self.assertIn("capture_vpn_snapshot", ast.get_source_segment(
            APP.read_text(encoding="utf-8"), methods["capture_vpn_from_dashboard"]))



if __name__ == "__main__":
    unittest.main()
