"""Verify the vector-derived PNG icon remains usable if Windows rejects ICO."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WindowIconFallbackTests(unittest.TestCase):
    def test_png_icon_is_not_guarded_by_windows_ico_try(self):
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and any(isinstance(m, ast.FunctionDef) and m.name == "set_window_icon" for m in n.body))
        method = next(m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == "set_window_icon")
        statements = method.body
        ico_if = next(i for i, n in enumerate(statements) if isinstance(n, ast.If) and "sys.platform" in ast.unparse(n.test))
        png_try = next(i for i, n in enumerate(statements) if isinstance(n, ast.Try) and "iconphoto" in ast.unparse(n))
        self.assertGreater(png_try, ico_if, "PNG icon must be attempted even after ICO load failure")
        self.assertNotIn("iconphoto", ast.unparse(statements[ico_if]), "ICO errors must not suppress PNG icon")


if __name__ == "__main__":
    unittest.main()
