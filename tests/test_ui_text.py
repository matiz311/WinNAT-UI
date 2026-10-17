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

    def test_generic_diagnostics_accessible_from_dashboard_and_information(self):
        source = APP.read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = {node.name: node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)}
        for name in ("build_dashboard", "build_about", "open_diagnostics",
                     "import_issue_dialog"):
            self.assertIn(name, methods)
        dashboard = ast.get_source_segment(source, methods["build_dashboard"])
        about = ast.get_source_segment(source, methods["build_about"])
        dialog = ast.get_source_segment(source, methods["open_diagnostics"])
        self.assertIn('text="Diagnostica e OpenIssue"', dashboard)
        self.assertIn("command=self.open_diagnostics", dashboard)
        self.assertIn("ui.ScrollFrame(page)", about)
        self.assertIn("Raccogli diagnostica", dialog)
        self.assertIn("Prepara anteprima", dialog)
        self.assertIn("submit_manual", dialog)
        self.assertIn("Aggiungi aggiornamento", dialog)
        self.assertNotIn("vpn_diagnostics", source)


if __name__ == "__main__":
    unittest.main()
