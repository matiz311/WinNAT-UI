"""Resize helpers: bursts of <Configure> events must collapse into little work."""
import tkinter as tk
import unittest

from winnat_ui import ui_theme as ui


class ResizeHelperTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # no display available
            self.skipTest("Tk non disponibile: %s" % exc)
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def settle(self, ms=120):
        self.root.after(ms, self.root.quit)
        self.root.mainloop()

    def test_burst_of_width_changes_runs_callback_once_with_last_width(self):
        frame = tk.Frame(self.root)
        calls = []
        handler = ui.on_width_change(frame, calls.append, delay=30)
        for width in (300, 310, 320, 330):
            handler(type("Event", (), {"widget": frame, "width": width})())
        self.assertEqual(calls, [])          # nothing runs synchronously
        self.settle()
        self.assertEqual(calls, [330])

    def test_height_only_changes_are_ignored(self):
        frame = tk.Frame(self.root)
        calls = []
        handler = ui.on_width_change(frame, calls.append, delay=10)
        handler(type("Event", (), {"widget": frame, "width": 400})())
        self.settle()
        for _ in range(5):                   # same width, e.g. only height changed
            handler(type("Event", (), {"widget": frame, "width": 400})())
        self.settle()
        self.assertEqual(calls, [400])

    def test_callback_after_destroy_does_not_raise(self):
        frame = tk.Frame(self.root)
        label = tk.Label(frame)
        handler = ui.on_width_change(frame, lambda w: label.configure(wraplength=w), delay=10)
        handler(type("Event", (), {"widget": frame, "width": 250})())
        label.destroy()
        self.settle()                        # TclError is swallowed

    def test_set_wrap_only_reconfigures_on_change(self):
        label = tk.Label(self.root, wraplength=200)
        configured = []
        original = label.configure
        label.configure = lambda **kw: (configured.append(kw), original(**kw))
        ui.set_wrap(label, 200)
        self.assertEqual(configured, [])
        ui.set_wrap(label, 260)
        self.assertEqual(configured, [{"wraplength": 260}])


if __name__ == "__main__":
    unittest.main()
