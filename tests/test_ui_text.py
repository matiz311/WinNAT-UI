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


if __name__ == "__main__":
    unittest.main()
