"""Real Tk geometry and consent checks; never contact GitHub or collect network data."""
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App
from winnat_ui import ui_theme as ui


class DiagnosticsDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            if sys.platform == "win32":
                raise
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        self.root.diagnostic_status_text = lambda: "Nessuna acquisizione"
        self.root.run_task = lambda *a, **kw: self.fail("Unexpected asynchronous submission")

    def open_dialog(self, scaling=1.0):
        self.root.tk.call("tk", "scaling", scaling)
        ui.apply(self.root, dark=False)
        App.open_diagnostics(self.root)
        self.window = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        self.root.update()
        return list(self.walk(self.window))

    def walk(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.walk(child)

    def button(self, widgets, text):
        return next(w for w in widgets if w.winfo_class() == "TButton" and w.cget("text") == text)

    def test_submit_actions_visible_at_small_window_and_high_scaling(self):
        for scaling in (1.0, 1.5, 2.0):
            with self.subTest(scaling=scaling):
                widgets = self.open_dialog(scaling)
                for geometry in ("980x760", "800x600", "640x400"):
                    self.window.geometry(geometry)
                    self.root.update()
                    for text in ("Prepara anteprima", "Aggiungi aggiornamento",
                                 "Invia nuova richiesta / OpenIssue"):
                        button = self.button(widgets, text)
                        self.assertTrue(button.winfo_ismapped(), (scaling, geometry, text))
                        x = button.winfo_rootx() - self.window.winfo_rootx()
                        y = button.winfo_rooty() - self.window.winfo_rooty()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + button.winfo_width(), self.window.winfo_width())
                        self.assertLessEqual(y + button.winfo_height(), self.window.winfo_height())
                self.window.destroy()

    def test_empty_report_never_submits(self):
        widgets = self.open_dialog()
        with patch("app.messagebox.showerror") as error, patch("app.issue_tracker.submit_manual") as submit:
            self.button(widgets, "Invia nuova richiesta / OpenIssue").invoke()
            error.assert_called_once()
            submit.assert_not_called()

    def test_cancelled_consent_keeps_draft_and_never_submits(self):
        widgets = self.open_dialog()
        # The first entry is the title; the larger Text is the report preview.
        entry = next(w for w in widgets if w.winfo_class() == "TEntry")
        entry.insert(0, "Richiesta di prova")
        preview = next(w for w in widgets if isinstance(w, tk.Text) and int(w.cget("height")) == 12)
        preview.insert("1.0", "Bozza privata modificata")
        with patch("app.messagebox.askyesno", return_value=False) as consent, \
                patch("app.issue_tracker.submit_manual") as submit:
            self.button(widgets, "Invia nuova richiesta / OpenIssue").invoke()
            consent.assert_called_once()
            submit.assert_not_called()
            self.assertEqual(preview.get("1.0", "end-1c"), "Bozza privata modificata")


if __name__ == "__main__":
    unittest.main()
