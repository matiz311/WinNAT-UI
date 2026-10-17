"""WinNAT UI - configuration-oriented Windows desktop interface."""
import ipaddress
import json
import queue
import sys
import threading
import traceback
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox, filedialog, simpledialog
from winnat_ui import network
from winnat_ui import nat_backend  # Include headless NAT/IP capabilities in packaged Windows executable.
from winnat_ui import secondary_ips
from winnat_ui import network_plan
from winnat_ui import network_guide
from winnat_ui import network_rollback
from winnat_ui import bug_report
from winnat_ui import issue_tracker
from winnat_ui import updater
from winnat_ui import ui_theme as ui
from version import VERSION
from winnat_ui.ui_theme import C, F, S1, S2, S3, S4, S5

REPO_URL = "https://github.com/matiz311/WinNAT-UI"
# Max wait for the update window before closing anyway (PowerShell + WinForms startup).
UPDATE_WINDOW_WAIT_MS = 15000

PAGES = [  # key, label, icon, subtitle
    ("dashboard", "Panoramica", "dashboard", "Stato reale della rete Windows, in sola lettura."),
    ("nat", "Regole NAT", "nat", "Regole WinNAT applicate e modifiche in attesa di Commit."),
    ("network", "Gateway", "network", "Trasforma il PC in un gateway LAN → NAT → WAN."),
    ("changes", "Modifiche", "changes", "Controlla le operazioni preparate prima di applicarle."),
    ("sessions", "Sessioni", "sessions", "Traduzioni NAT attive in questo momento."),
    ("about", "Informazioni", "info", "Versione, scorciatoie e note di sicurezza."),
]
FIELD_TITLES = {"lan": "LAN", "prefix": "Subnet LAN", "gateway": "IP del PC", "nat": "Nome NAT"}


def field_title(key):
    """Readable name for static fields and dynamic WAN rows ("wan:0", "metric:1")."""
    if ":" in key:
        kind, index = key.split(":")
        return ("WAN " if kind == "wan" else "Metrica WAN ") + str(int(index) + 1)
    return FIELD_TITLES.get(key, key)
ADAPTER_STATUS = {"Up": "Connessa", "Disconnected": "Disconnessa", "Disabled": "Disabilitata",
                  "Not Present": "Assente", "Down": "Inattiva"}
PROTOCOLS = {1: "ICMP", 6: "TCP", 17: "UDP", "1": "ICMP", "6": "TCP", "17": "UDP"}


def is_on(value):
    return value in (1, "1", True, "Enabled", "True", "true")


def yes_no(value):
    if value in (None, ""):
        return "—"
    return "Sì" if is_on(value) else "No"


def service_status(value):
    return {1: "Arrestato", 4: "In esecuzione", "Stopped": "Arrestato",
            "Running": "In esecuzione"}.get(value, str(value or "sconosciuto"))


def friendly_ip_error(exc, example):
    text = str(exc)
    if "host bits" in text:
        return "Usa l'indirizzo di rete, non un host (es. " + example + ")."
    if any(word in text for word in ("does not appear", "Expected", "Octet", "octet", "Only decimal")):
        return "Formato non valido (es. " + example + ")."
    return text


class Dialog(tk.Toplevel):
    """Modal dialog with explicit verb buttons (no ambiguous Si/No)."""

    def __init__(self, app, title, confirm, kind="Accent", cancel="Annulla"):
        super().__init__(app)
        self.app, self.result = app, False
        self.title(title)
        self.configure(bg=C["surface"])
        self.transient(app)
        self.resizable(False, False)
        self.body = tk.Frame(self, bg=C["surface"])
        self.body.pack(fill="both", expand=True, padx=S5, pady=(S5, S4))
        ttk.Label(self.body, text=title, style="Card.Title.TLabel").pack(anchor="w", pady=(0, S3))
        bar = tk.Frame(self, bg=C["surface_alt"], highlightthickness=0)
        bar.pack(fill="x", side="bottom")
        tk.Frame(bar, bg=C["border"], height=1).pack(fill="x", side="top")
        self.ok = ttk.Button(bar, text=confirm, style=kind + ".TButton", command=self.accept)
        self.ok.pack(side="right", padx=(S2, S5), pady=S3)
        cancel_btn = ttk.Button(bar, text=cancel, command=self.destroy)
        cancel_btn.pack(side="right", pady=S3)
        self.bind("<Escape>", lambda e: self.destroy())
        self.cancel_btn = cancel_btn

    def accept(self):
        if str(self.ok["state"]) == "disabled":
            return
        self.result = True
        self.destroy()

    def recenter(self):
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_reqwidth()) // 2
        y = self.app.winfo_rooty() + (self.app.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    def run(self, focus=None):
        self.recenter()
        self.grab_set()
        (focus or self.cancel_btn).focus_set()
        self.wait_window()
        return self.result


class ProgressDialog(tk.Toplevel):
    """Modal "sending" window for a background task.

    Shows an indeterminate bar while the work runs, then the outcome in the
    same window: success closes itself after ``auto_close_ms`` (and runs
    ``on_success_close``), failure stays open with Riprova / Chiudi so the
    person decides. It cannot be dismissed while the request is in flight.
    """
    AUTO_CLOSE_MS = 2500

    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.parent = parent
        self.busy = True
        self.title(title)
        self.configure(bg=C["surface"])
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        body = tk.Frame(self, bg=C["surface"])
        body.pack(fill="both", expand=True, padx=S5, pady=(S5, S4))
        self.heading = ttk.Label(body, text=title, style="Card.Title.TLabel")
        self.heading.pack(anchor="w", pady=(0, S3))
        self.message = tk.Label(body, text=message, font=F["body"], bg=C["surface"], fg=C["text"],
                                wraplength=420, justify="left", anchor="w")
        self.message.pack(fill="x", anchor="w")
        self.bar = ttk.Progressbar(body, mode="indeterminate", length=420)
        self.bar.pack(fill="x", pady=(S3, 0))
        self.link = tk.Label(body, font=F["body"], bg=C["surface"], fg=C["accent"], cursor="hand2",
                             anchor="w")
        self.footer = tk.Frame(self, bg=C["surface_alt"], highlightthickness=0)
        tk.Frame(self.footer, bg=C["border"], height=1).pack(fill="x", side="top")
        self.primary = ttk.Button(self.footer, text="Chiudi", style="Accent.TButton", command=self.close)
        self.primary.pack(side="right", padx=(S2, S5), pady=S3)
        self.secondary = ttk.Button(self.footer, text="Riprova")
        self.on_close = None
        self.bar.start(11)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
        self.grab_set()
        self.focus_set()

    def _finish(self, heading, text, color):
        self.busy = False
        self.bar.stop()
        self.bar.pack_forget()
        self.heading.configure(text=heading)
        self.message.configure(text=text, fg=color)
        self.footer.pack(fill="x", side="bottom")

    def succeed(self, heading, text, url=None, on_close=None, auto_close_ms=AUTO_CLOSE_MS):
        self._finish(heading, text, C["success"])
        if url:
            self.link.configure(text=url)
            self.link.bind("<Button-1>", lambda e: webbrowser.open(url))
            self.link.pack(fill="x", anchor="w", pady=(S2, 0))
        self.on_close = on_close
        self.primary.focus_set()
        self.after(auto_close_ms, self.close)

    def fail(self, heading, text, retry=None):
        self._finish(heading, text, C["danger"])
        if retry is not None:
            self.secondary.configure(command=lambda: (self._close_window(), retry()))
            self.secondary.pack(side="right", pady=S3)
        self.primary.focus_set()

    def _close_window(self):
        if not self.winfo_exists():
            return
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        try:
            if self.parent.winfo_exists():
                self.parent.grab_set()
                self.parent.focus_set()
        except tk.TclError:
            pass

    def close(self):
        if self.busy or not self.winfo_exists():
            return
        self._close_window()
        callback, self.on_close = self.on_close, None
        if callback:
            callback()


class Topology(tk.Canvas):
    """Live sketch of LAN \u2192 PC gateway \u2192 WAN(s) \u2192 Internet built from the form values.

    It turns abstract fields into a picture the user can check at a glance
    (recognition rather than recall): wrong interface = wrong arrow.
    """
    H = 196

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["surface"], highlightthickness=0, height=self.H)
        self.app = app
        # Redraw on width changes only, coalesced while the window is dragged.
        ui.on_width_change(self, lambda w: self.draw())

    def node(self, x, y, w, h, title, sub, color, dashed=False, fill=None):
        self.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2, outline=color, width=2,
                              fill=fill or C["surface"], dash=(4, 3) if dashed else None)
        self.create_text(x, y - 9, text=title, fill=C["text"], font=F["body_b"], width=w - 12)
        self.create_text(x, y + 11, text=sub, fill=C["text_muted"], font=F["caption"], width=w - 12)

    def chip(self, x, y, text, color):
        tid = self.create_text(x, y, text=text, fill=color, font=F["overline"])
        box = self.bbox(tid)
        if box:
            rid = self.create_rectangle(box[0] - 6, box[1] - 2, box[2] + 6, box[3] + 2, fill=C["surface"], outline=color)
            self.tag_lower(rid, tid)

    def draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 560)
        a = self.app
        wans = [(row["alias"].get(), row["metric"].get()) for row in a.wan_rows] or [("", "")]
        lan = a.lan.get() or "LAN ?"
        prefix, gateway = a.prefix.get() or "?", a.gateway.get() or "?"
        n = len(wans)
        gap = 52
        height = max(self.H, 92 + n * gap)
        if int(self.cget("height")) != height:   # avoid a relayout when unchanged
            self.configure(height=height)
        col = [w * 0.11, w * 0.40, w * 0.69, w * 0.90]
        nw = min(170, w * 0.17)
        top = 18
        mid = (height - 34) / 2 + 8
        for x, text in ((col[0], "RETE LAN"), (col[1], "QUESTO PC"), ((col[2] + col[3]) / 2, "USCITA INTERNET")):
            self.create_text(x, top, text=text, fill=C["text_faint"], font=F["overline"])
        self.create_line(col[0] + nw / 2, mid, col[1] - nw / 2 - 6, mid, fill=C["accent"], width=3, arrow="last",
                         arrowshape=(10, 12, 5))
        bad = getattr(self, "errors", {})
        self.node(col[0], mid, nw, 56, "Client / firewall", prefix,
                  C["danger"] if "prefix" in bad else C["border_strong"])
        self.node(col[1], mid, nw + 20, 64, "Gateway NAT", gateway,
                  C["danger"] if "gateway" in bad else C["accent"],
                  fill=C["danger_soft"] if "gateway" in bad else C["accent_soft"])
        self.chip((col[0] + col[1]) / 2, mid - 18, lan, C["accent"])
        x_out = col[1] + (nw + 20) / 2
        cx, r = col[3], min(44, w * 0.05)
        ys = [mid + (i - (n - 1) / 2) * gap for i in range(n)]
        for i, ((alias, metric), y) in enumerate(zip(wans, ys)):
            primary = i == 0
            color = C["danger"] if ("wan:%d" % i) in bad or ("metric:%d" % i) in bad else (
                C["info"] if primary else C["text_faint"])
            dash = None if primary else (6, 4)
            self.create_line(x_out, mid, col[2] - nw / 2, y, fill=color, width=3 if primary else 2, dash=dash)
            self.node(col[2], y, nw, 44, alias or "WAN ?",
                      ("primaria" if primary else "riserva %d" % i) + " \u00b7 metrica " + (metric or "?"),
                      color, dashed=not primary)
            self.create_line(col[2] + nw / 2, y, cx - r, mid, fill=color, width=3 if primary else 2, dash=dash,
                             arrow="last" if primary else None, arrowshape=(10, 12, 5))
        for dx, dy, k in ((-0.5, 0.15, 0.7), (0.05, -0.25, 0.85), (0.55, 0.12, 0.65), (0, 0.35, 0.7)):
            self.create_oval(cx + dx * r - k * r, mid + dy * r - k * r, cx + dx * r + k * r, mid + dy * r + k * r,
                             fill=C["surface_alt"], outline=C["border_strong"])
        for dx, dy, k in ((-0.5, 0.15, 0.7), (0.05, -0.25, 0.85), (0.55, 0.12, 0.65), (0, 0.35, 0.7)):
            self.create_oval(cx + dx * r - k * r + 2, mid + dy * r - k * r + 2, cx + dx * r + k * r - 2,
                             mid + dy * r + k * r - 2, fill=C["surface_alt"], outline="")
        self.create_text(cx, mid + 4, text="Internet", fill=C["text"], font=F["caption"])
        self.create_text(w / 2, height - 16, fill=C["text_muted"], font=F["caption"], width=w - 40,
                         text="I client usano " + gateway + " come gateway e un DNS raggiungibile: "
                              "WinNAT non fornisce DHCP n\u00e9 DNS.")


def format_error_debug(operation, message, traceback_text=""):
    """Retain the complete error and Python traceback for copying/debugging."""
    return ("Operazione: " + str(operation) + "\n\n" +
            "Messaggio completo:\n" + str(message) + "\n\n" +
            "Traceback Python:\n" + (traceback_text or "Non disponibile"))


def error_summary(message):
    """First line a person can act on: prefer the PowerShell error text over headers."""
    text = str(message)
    for marker in ("STDERR (integrale):", "STDERR:"):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    skip = ("PowerShell exit code", "ESECUZIONE POWERSHELL", "Exit code:", "Interprete:", "Timeout configurato:",
            "STDERR", "STDOUT", "SCRIPT ESEGUITO", "In riga:", "At line:", "+ ", "~", "(vuoto)")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(skip):
            return line[:300] + ("\u2026" if len(line) > 300 else "")
    return "Errore sconosciuto: apri i dettagli tecnici."


def resource_path(*parts):
    """Bundled file path both from source and from the PyInstaller build."""
    import os
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


class App(tk.Tk):
    def __init__(self):
        ui.enable_dpi_awareness()
        super().__init__()
        ui.apply(self)
        self.title("WinNAT UI " + VERSION)
        self.set_window_icon()
        self.geometry("1200x800")
        self.minsize(1000, 660)
        self.data = None
        self.pending = []
        self.work = queue.Queue()
        self.tasks = set()
        self.is_admin = network.admin()
        self.current = None
        self.session_rows = []
        self.toast = ui.Toast(self)
        self.build()
        self.bind_shortcuts()
        self.show_page("dashboard")
        self.after(100, self.drain)
        self.after(60000, self.periodic_sessions)
        # A failed update saved by the helper is offered for reporting once; in
        # that session the automatic update prompt is skipped to avoid a loop.
        self.update_failure = updater.pending_failure()
        if self.update_failure:
            self.after(1200, self.report_update_failure)
        else:
            self.after(2500, lambda: self.check_updates(silent=True))
        self.after(7000, lambda: self.refresh_issue_tracker(silent=True))
        self.refresh()

    def set_window_icon(self):
        """Title bar, taskbar and every dialog use the app icon; never fatal."""
        self.logo = None
        # The Windows ICO and Tk PNG are independent: an unavailable or
        # rejected ICO must not prevent the PNG from reaching Tk dialogs.
        if sys.platform == "win32":
            try:
                self.iconbitmap(default=resource_path("assets", "winnat-ui.ico"))
            except (tk.TclError, OSError):
                pass
        try:
            self.iconphoto(True, tk.PhotoImage(file=resource_path("assets", "winnat-ui-256.png")))
        except (tk.TclError, OSError):
            pass
        try:
            self.logo = tk.PhotoImage(file=resource_path("assets", "winnat-ui-32.png"))
        except (tk.TclError, OSError):
            self.logo = None

    # ------------------------------------------------------------ layout --
    def build(self):
        side = tk.Frame(self, bg=C["side_bg"], width=228)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = ttk.Frame(side, style="Side.TFrame")
        brand.pack(fill="x", padx=S4, pady=(S5, S4))
        if self.logo is not None:
            tk.Label(brand, image=self.logo, bg=C["side_bg"], bd=0).pack(side="left", padx=(0, S2))
        else:
            ttk.Label(brand, text=ui.icon("network"), style="Side.Logo.TLabel").pack(side="left", padx=(0, S2))
        names = ttk.Frame(brand, style="Side.TFrame")
        names.pack(side="left")
        ttk.Label(names, text="WinNAT UI", style="Side.Brand.TLabel").pack(anchor="w")
        ttk.Label(names, text="Gateway & NAT", style="Side.Caption.TLabel").pack(anchor="w")
        ttk.Separator(side, style="Side.TSeparator").pack(fill="x", padx=S4, pady=(0, S3))
        self.nav = {}
        for i, (key, label, glyph, _sub) in enumerate(PAGES):
            if key == "about":
                ttk.Frame(side, style="Side.TFrame").pack(fill="both", expand=True)
            row = tk.Frame(side, bg=C["side_bg"])
            row.pack(fill="x", padx=(0, S3), pady=1)
            marker = tk.Frame(row, bg=C["side_bg"], width=3)
            marker.pack(side="left", fill="y", padx=(0, S3))
            btn = ttk.Button(row, text="  " + label, style="Nav.TButton", takefocus=True,
                             command=lambda k=key: self.show_page(k))
            btn.pack(side="left", fill="x", expand=True)
            glyph_label = tk.Label(row, text=ui.icon(glyph), font=F["icon"], bg=C["side_bg"], fg=C["side_muted"])
            glyph_label.place(in_=btn, x=S3, rely=0.5, anchor="w")
            glyph_label.bind("<Button-1>", lambda e, k=key: self.show_page(k))
            count = tk.Label(row, text="", font=F["overline"], bg=C["warning"], fg="#FFFFFF", padx=6)
            self.nav[key] = (btn, marker, glyph_label, count)
            btn.configure(text="       " + label)
        status = tk.Frame(side, bg=C["side_bg"])
        status.pack(fill="x", side="bottom", padx=S4, pady=S4)
        role_kind = "success" if self.is_admin else "warning"
        tk.Label(status, text=ui.icon("shield"), font=F["icon"], bg=C["side_bg"],
                 fg=C[role_kind]).grid(row=0, column=0, sticky="w", padx=(0, S2))
        tk.Label(status, text="Amministratore" if self.is_admin else "Sola lettura", font=F["body_b"],
                 bg=C["side_bg"], fg=C["side_text"]).grid(row=0, column=1, sticky="w")
        if not self.is_admin:
            tk.Label(status, text="Riavvia come amministratore\nper applicare modifiche.", justify="left",
                     font=F["caption"], bg=C["side_bg"], fg=C["side_muted"]).grid(row=1, column=1, sticky="w")
        self.notice = tk.StringVar(value="Caricamento configurazione…")
        tk.Label(status, textvariable=self.notice, font=F["caption"], bg=C["side_bg"], fg=C["side_muted"],
                 wraplength=180, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(S2, 0))

        main = ttk.Frame(self)
        main.pack(side="left", fill="both", expand=True)
        self.progress = ttk.Progressbar(main, mode="determinate", value=0, style="Thin.Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        self.build_changebar(main)
        self.stack = ttk.Frame(main)
        self.stack.pack(fill="both", expand=True)
        self.pages = {}
        builders = dict(dashboard=self.build_dashboard, nat=self.build_nat, network=self.build_network,
                        changes=self.build_changes, sessions=self.build_sessions, about=self.build_about)
        for key, label, _glyph, sub in PAGES:
            page = ttk.Frame(self.stack, padding=(S5 + S1, S4, S5 + S1, S4))
            self.pages[key] = page
            head = ttk.Frame(page)
            head.pack(fill="x", pady=(0, S4))
            words = ttk.Frame(head)
            words.pack(side="left")
            ttk.Label(words, text=label, style="Display.TLabel").pack(anchor="w")
            ttk.Label(words, text=sub, style="Muted.TLabel").pack(anchor="w", pady=(S1, 0))
            page.actions = ttk.Frame(head)
            page.actions.pack(side="right", anchor="s")
            builders[key](page)

    def build_changebar(self, parent):
        """Persistent bottom bar: the one place where pending changes are applied."""
        self.changebar = tk.Frame(parent, bg=C["surface"], highlightthickness=0)
        self.changebar.pack(fill="x", side="bottom")
        self.changebar_line = tk.Frame(self.changebar, bg=C["border"], height=1)
        self.changebar_line.pack(fill="x", side="top")
        inner = tk.Frame(self.changebar, bg=C["surface"])
        inner.pack(fill="x", padx=S5 + S1, pady=S3)
        self.cb_icon = tk.Label(inner, font=F["icon"], bg=C["surface"])
        self.cb_icon.pack(side="left", padx=(0, S2))
        texts = tk.Frame(inner, bg=C["surface"])
        texts.pack(side="left", fill="x", expand=True)
        self.cb_texts = texts
        ui.on_width_change(texts, lambda w: (ui.set_wrap(self.cb_title, max(200, w)),
                                             ui.set_wrap(self.cb_hint, max(200, w))))
        self.cb_title = tk.Label(texts, font=F["body_b"], bg=C["surface"], fg=C["text"], anchor="w")
        self.cb_title.pack(anchor="w")
        self.cb_hint = tk.Label(texts, font=F["caption"], bg=C["surface"], fg=C["text_muted"], anchor="w")
        self.cb_hint.pack(anchor="w")
        self.commit_button = ttk.Button(inner, text="Applica…", style="Accent.TButton", command=self.commit)
        self.commit_button.pack(side="right")
        self.review_button = ttk.Button(inner, text="Rivedi", command=lambda: self.show_page("changes"))
        self.review_button.pack(side="right", padx=S2)
        self.discard_button = ttk.Button(inner, text="Scarta", command=self.discard)
        self.discard_button.pack(side="right")
        self.cb_widgets = [self.changebar, inner, texts, self.cb_icon, self.cb_title, self.cb_hint]

    def section(self, parent, title, hint=None):
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=(S4, S2))
        ttk.Label(box, text=title.upper(), style="Overline.TLabel").pack(side="left")
        if hint:
            ttk.Label(box, text="  ·  " + hint, style="Caption.TLabel").pack(side="left")
        return box

    # --------------------------------------------------------- dashboard --
    def build_dashboard(self, page):
        ttk.Button(page.actions, text="Esporta JSON", command=self.export).pack(side="right")
        ttk.Button(page.actions, text="Aggiorna  (F5)",
                   command=self.refresh).pack(side="right", padx=S2)
        scroll = ui.ScrollFrame(page)
        scroll.pack(fill="both", expand=True)
        body = scroll.inner
        self.hero = ui.Card(body, edge=C["border_strong"], padding=S4)
        self.hero.pack(fill="x")
        self.hero_title = tk.Label(self.hero.body, font=F["title"], bg=C["surface"], fg=C["text"], anchor="w")
        self.hero_title.pack(side="left", anchor="w")
        self.hero_text = tk.Label(self.hero.body, font=F["body"], bg=C["surface"], fg=C["text_muted"], anchor="w")
        self.hero_text.pack(side="left", padx=S4)
        self.hero_cta = ttk.Button(self.hero.body, text="Configura gateway", style="Accent.TButton",
                                   command=lambda: self.show_page("network"))
        self.hero_edge = self.hero.winfo_children()[0]

        grid = ttk.Frame(body)
        grid.pack(fill="x", pady=(S3, 0))
        self.kpis = {}
        for col, (key, label) in enumerate([("wan", "WAN predefinita"), ("nat", "WinNAT"),
                                             ("router", "Routing IPv4"), ("ics", "Condivisione ICS")]):
            grid.columnconfigure(col, weight=1, uniform="kpi")
            card = ui.Card(grid, padding=S4)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else S2, 0))
            top = tk.Frame(card.body, bg=C["surface"])
            top.pack(fill="x")
            tk.Label(top, text=label.upper(), font=F["overline"], bg=C["surface"], fg=C["text_muted"]).pack(side="left")
            badge = ui.Badge(top, "…")
            badge.pack(side="right")
            value = tk.Label(card.body, text="—", font=F["kpi"], bg=C["surface"], fg=C["text"], anchor="w")
            value.pack(anchor="w", pady=(S2, 0))
            detail = tk.Label(card.body, text="", font=F["caption"], bg=C["surface"], fg=C["text_muted"],
                              anchor="w", justify="left", wraplength=200)
            detail.pack(anchor="w")
            self.kpis[key] = (badge, value, detail)

        self.dash_pending = ui.Callout(body, kind="warning")
        self.dash_pending.label.bind("<Button-1>", lambda e: self.show_page("changes"))

        self.dash_iface_head = self.section(body, "Interfacce di rete", "il ruolo LAN/WAN segue la selezione in Gateway")
        wrap, self.iface_table = ui.make_table(body, [("name", "Interfaccia", 170), ("role", "Ruolo", 90),
            ("status", "Stato", 120), ("ipv4", "IPv4", 220), ("dhcp", "DHCP", 70), ("fwd", "Forwarding", 100),
            ("metric", "Metrica", 80)], height=6)
        wrap.pack(fill="x")
        self.section(body, "Default route", "la WAN prevista è quella con metrica totale più bassa")
        wrap, self.route_table = ui.make_table(body, [("iface", "Interfaccia", 200), ("hop", "Next hop", 220),
            ("route", "Metrica route", 120), ("ifm", "Metrica interfaccia", 150), ("tot", "Totale", 100)], height=3)
        wrap.pack(fill="x")

        tech = self.section(body, "Dettagli tecnici")
        self.tech_open = tk.BooleanVar(value=False)
        self.tech_toggle = ttk.Button(tech, text="Mostra", style="Ghost.TButton", command=self.toggle_tech)
        self.tech_toggle.pack(side="left", padx=S2)
        self.dashboard = tk.Text(body, height=14, font=F["mono_s"], state="disabled", wrap="word", bd=0,
                                 bg=C["surface"], fg=C["text"], padx=S4, pady=S3, highlightthickness=1,
                                 highlightbackground=C["border"], insertbackground=C["text"])

    def toggle_tech(self):
        if self.dashboard.winfo_ismapped():
            self.dashboard.pack_forget()
            self.tech_toggle.configure(text="Mostra")
        else:
            self.dashboard.pack(fill="x", pady=(0, S4))
            self.tech_toggle.configure(text="Nascondi")

    # -------------------------------------------------------------- NAT ---
    def build_nat(self, page):
        self.remove_button = ttk.Button(page.actions, text="Elimina", command=self.remove, state="disabled")
        self.remove_button.pack(side="right")
        ttk.Button(page.actions, text="+  Aggiungi regola", style="Accent.TButton",
                   command=self.add).pack(side="right", padx=S2)
        ui.Callout(page, kind="info", wraplength=900,
                   text="Windows WinNAT supporta ufficialmente un solo prefisso interno. "
                        "Le operazioni restano in attesa: la rete cambia solo quando premi Applica.").pack(fill="x", pady=(0, S3))
        holder = ttk.Frame(page)
        holder.pack(fill="both", expand=True)
        wrap, self.nat_table = ui.make_table(holder, [("state", "Stato", 150), ("name", "Nome", 240),
            ("prefix", "Subnet interna", 240), ("active", "Attiva", 100)], height=12)
        wrap.pack(fill="both", expand=True)
        self.nat_table.bind("<<TreeviewSelect>>", self.nat_selected)
        self.nat_table.bind("<Delete>", lambda e: self.remove())
        self.nat_empty = tk.Frame(wrap, bg=C["surface"])
        tk.Label(self.nat_empty, text=ui.icon("nat"), font=F["icon_l"], bg=C["surface"], fg=C["text_faint"]).pack()
        tk.Label(self.nat_empty, text="Nessuna regola WinNAT", font=F["strong"], bg=C["surface"], fg=C["text"]).pack(pady=(S2, 0))
        tk.Label(self.nat_empty, text="Il modo più sicuro per crearne una è la configurazione guidata del gateway.",
                 font=F["body"], bg=C["surface"], fg=C["text_muted"]).pack(pady=(S1, S3))
        ttk.Button(self.nat_empty, text="Apri Gateway", style="CardGhost.TButton",
                   command=lambda: self.show_page("network")).pack()

    def nat_selected(self, _event=None):
        sel = self.nat_table.selection()
        if not sel:
            self.remove_button.configure(state="disabled", text="Elimina")
            return
        values = self.nat_table.item(sel[0], "values")
        pending_add = str(values[0]).startswith("+")
        locked = str(values[0]).startswith("-")
        self.remove_button.configure(state="disabled" if locked else "normal",
                                     text="Annulla aggiunta" if pending_add else "Elimina")

    # ---------------------------------------------------------- gateway ---
    def build_network(self, page):
        self.lan = tk.StringVar(value="Ethernet")
        self.prefix = tk.StringVar(value=network_guide.DEFAULT_PREFIX)
        self.gateway = tk.StringVar(value=network_guide.DEFAULT_GATEWAY)
        self.profile_nat = tk.StringVar(value="NAT-Firewall")
        self.wan_rows = []
        self.subnet_detected_for = None

        seg = ttk.Frame(page)
        seg.pack(fill="x", pady=(0, S3))
        self.seg_buttons = {}
        for key, text in (("setup", "Configura gateway"), ("teardown", "Disabilita / Ripristina")):
            b = ttk.Button(seg, text=text, style="Seg.TButton", command=lambda k=key: self.show_mode(k))
            b.pack(side="left")
            self.seg_buttons[key] = b
        self.wizard_notice = tk.StringVar(value="")
        self.modes = {}

        scroll = ui.ScrollFrame(page)
        scroll.pack(fill="both", expand=True)
        setup = ttk.Frame(scroll.inner)
        self.modes["setup"] = setup
        setup.columnconfigure(0, weight=1, uniform="g")
        setup.columnconfigure(1, weight=1, uniform="g")
        topo_card = ui.Card(setup, padding=S3)
        topo_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, S3))
        self.topology = Topology(topo_card.body, self)
        self.topology.pack(fill="x")
        form_card = ui.Card(setup, padding=S5)
        form_card.grid(row=1, column=0, sticky="nsew", padx=(0, S3))
        form = form_card.body
        form.columnconfigure(0, weight=1, uniform="f")
        form.columnconfigure(1, weight=1, uniform="f")
        self.field_errors = {}
        self.field_widgets = {}
        row = [0]
        # (label, divisor, margin, minimum): rewrapped together by one throttled
        # handler instead of one <Configure> binding per label.
        form_wraps = []

        def heading(n, text):
            top = S5 if row[0] else 0
            box = tk.Frame(form, bg=C["surface"])
            box.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(top, S2))
            tk.Label(box, text=n, font=F["overline"], bg=C["accent"], fg=C["accent_text"], width=2).pack(side="left")
            ttk.Label(box, text=text, style="Card.Strong.TLabel").pack(side="left", padx=S2)
            row[0] += 1

        def field(key, title, variable, combo=False, hint="", col=0, span=2, newrow=True):
            # Labels sit above inputs: one vertical scan path, room for long hints.
            r = row[0]
            pad = (0, S2) if (span == 1 and col == 0) else 0
            ttk.Label(form, text=title, style="Card.TLabel").grid(row=r, column=col, columnspan=span, sticky="w",
                                                                 pady=(S2, 2), padx=pad)
            control = (ttk.Combobox(form, textvariable=variable, state="readonly")
                       if combo else ttk.Entry(form, textvariable=variable))
            control.grid(row=r + 1, column=col, columnspan=span, sticky="ew", padx=pad)
            msg = ttk.Label(form, text=hint, style="Card.Caption.TLabel", justify="left",
                            wraplength=200 if span == 1 else 420)
            msg.grid(row=r + 2, column=col, columnspan=span, sticky="w", pady=(2, 0), padx=pad)
            form_wraps.append((msg, 2 if span == 1 else 1, 16, 120))
            if newrow:
                row[0] += 3
            self.field_errors[key] = (msg, hint)
            self.field_widgets[key] = control
            variable.trace_add("write", lambda *a: self.validate_form())
            return control

        heading("1", "Rete LAN")
        self.lan_box = field("lan", "Interfaccia LAN \u2014 verso i client", self.lan, True,
                             "Scheda collegata al firewall o allo switch")
        self.lan.trace_add("write", lambda *a: self.on_lan_changed())
        self.subnet_badge = ui.Badge(form, "", "neutral")
        self.subnet_badge.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(S3, 0))
        row[0] += 1
        field("prefix", "Subnet LAN (CIDR)", self.prefix, hint="", col=0, span=1, newrow=False)
        self.prefix.trace_add("write", lambda *a: self.follow_prefix())
        field("gateway", "IP del PC sulla LAN", self.gateway, hint="Statico, senza gateway", col=1, span=1)
        self.subnet_hint = ttk.Label(form, text="", style="Card.Caption.TLabel", wraplength=420, justify="left")
        self.subnet_hint.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(0, S1))
        row[0] += 1
        field("nat", "Nome regola NAT", self.profile_nat, hint="Lettere, numeri, - e _")

        # This editor manages existing LAN secondary addresses separately from
        # the gateway wizard. No network write occurs before Commit.
        ttk.Label(form, text="INDIRIZZI IPv4 SECONDARI DELLA LAN",
                  style="Card.Overline.TLabel").grid(
                      row=row[0], column=0, columnspan=2, sticky="w", pady=(S4, S1))
        row[0] += 1
        secondary_wrap, self.secondary_table = ui.make_table(
            form, [("ip", "Indirizzo IPv4", 150), ("prefix", "Prefisso", 70),
                   ("role", "Ruolo / stato", 210)], height=4)
        secondary_wrap.grid(row=row[0], column=0, columnspan=2, sticky="ew")
        self.secondary_table.bind("<<TreeviewSelect>>", self.secondary_selected)
        row[0] += 1
        self.secondary_rows = {}
        secondary_actions = ttk.Frame(form)
        secondary_actions.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(S2, S1))
        ttk.Button(secondary_actions, text="+  Aggiungi Secondary IP",
                   style="CardGhost.TButton", command=lambda: self.prepare_secondary("add")).pack(side="left")
        self.secondary_edit_button = ttk.Button(secondary_actions, text="Modifica",
                   command=lambda: self.prepare_secondary("edit"), state="disabled")
        self.secondary_edit_button.pack(side="left", padx=S2)
        self.secondary_remove_button = ttk.Button(secondary_actions, text="Rimuovi",
                   command=lambda: self.prepare_secondary("remove"), state="disabled")
        self.secondary_remove_button.pack(side="left")
        row[0] += 1
        ttk.Label(form,
                  text="Solo IPv4 secondari (SkipAsSource): l'IP principale, DHCP, gateway e route "
                       "non vengono modificati. Per altre subnet verifica la copertura del prefisso WinNAT.",
                  style="Card.Caption.TLabel", wraplength=430, justify="left").grid(
                      row=row[0], column=0, columnspan=2, sticky="w", pady=(0, S2))
        row[0] += 1
        heading("2", "Uscite Internet (WAN)")
        wan_intro = ttk.Label(form, text="In ordine di priorit\u00e0: la prima \u00e8 la primaria, le altre "
                                         "subentrano se cade quella sopra. Metrica pi\u00f9 bassa = preferita.",
                              style="Card.Caption.TLabel", wraplength=420, justify="left")
        wan_intro.grid(row=row[0], column=0, columnspan=2, sticky="w")
        form_wraps += [(wan_intro, 1, 8, 200), (self.subnet_hint, 1, 8, 200)]
        ui.on_width_change(form, lambda w: [ui.set_wrap(lbl, max(low, (w - margin) // div))
                                            for lbl, div, margin, low in form_wraps])
        row[0] += 1
        self.wan_frame = tk.Frame(form, bg=C["surface"])
        self.wan_frame.grid(row=row[0], column=0, columnspan=2, sticky="ew", pady=(S2, 0))
        self.wan_frame.columnconfigure(1, weight=1)
        row[0] += 1
        add_bar = tk.Frame(form, bg=C["surface"])
        add_bar.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(S2, 0))
        row[0] += 1
        self.add_wan_button = ttk.Button(add_bar, text="+  Aggiungi WAN", style="CardGhost.TButton",
                                         command=self.add_wan_row)
        self.add_wan_button.pack(side="left")
        self.add_wan_hint = ttk.Label(add_bar, text="", style="Card.Caption.TLabel")
        self.add_wan_hint.pack(side="left", padx=S2)
        self.add_wan_row("USB-C", "10", validate=False)
        ttk.Button(form, text="Ripristina valori consigliati", style="CardGhost.TButton",
                   command=self.reset_form).grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(S4, 0))

        plan_card = ui.Card(setup, padding=S5)
        plan_card.grid(row=1, column=1, sticky="nsew")
        ttk.Label(plan_card.body, text="COSA SUCCEDER\u00c0 AL COMMIT", style="Card.Overline.TLabel").pack(anchor="w")
        self.plan_list = tk.Frame(plan_card.body, bg=C["surface"])
        self.plan_list.pack(fill="x", pady=(S2, S3))
        self.plan_labels = []
        ui.on_width_change(self.plan_list, lambda w: [ui.set_wrap(t, self.plan_wrap_width(w))
                                                      for t in self.plan_labels if t.winfo_exists()])
        self.setup_issue = ui.Callout(plan_card.body, kind="danger", wraplength=440)
        actions = tk.Frame(plan_card.body, bg=C["surface"])
        actions.pack(fill="x", side="bottom")
        self.prepare_button = ttk.Button(actions, text="Prepara configurazione", style="Accent.TButton",
                                         command=lambda: self.prepare_guide("apply"))
        self.prepare_button.pack(side="left")
        tk.Label(actions, text="Nulla viene applicato finché non premi Applica.", font=F["caption"],
                 bg=C["surface"], fg=C["text_muted"]).pack(side="left", padx=S3)

        tear = ttk.Frame(scroll.inner)
        self.modes["teardown"] = tear
        self.scope_label = ui.Callout(tear, kind="info", wraplength=900)
        self.scope_label.pack(fill="x", pady=(0, S3))
        self.teardown_issue = ui.Callout(tear, kind="danger", wraplength=900)
        for action, title, edge, style, bullets, button in (
            ("disable", "Disabilita il gateway", C["warning"], "TButton",
             ["Elimina TUTTI gli oggetti WinNAT, anche quelli creati da Hyper-V, WSL o altre app",
              "Disabilita il forwarding sulle interfacce selezionate e IPEnableRouter",
              "Conserva IP, DHCP, route e metriche"], "Prepara disabilitazione"),
            ("reset", "Ripristina la configurazione di rete", C["danger"], "Danger.TButton",
             ["Tutto ciò che fa «Disabilita», in più:",
              "Rimuove tutti gli IPv4 e le route della LAN e riattiva il suo DHCP",
              "Riporta le WAN selezionate alle metriche automatiche",
              "Se il commit fallisce, tenta il rollback delle sole risorse coinvolte"], "Prepara ripristino")):
            card = ui.Card(tear, edge=edge, padding=S4)
            card.pack(fill="x", pady=(0, S3))
            ttk.Label(card.body, text=title, style="Card.Strong.TLabel").pack(anchor="w")
            for b in bullets:
                tk.Label(card.body, text="•  " + b, font=F["body"], bg=C["surface"], fg=C["text_muted"],
                         anchor="w", justify="left").pack(anchor="w", pady=(S1, 0))
            ttk.Button(card.body, text=button, style=style,
                       command=lambda a=action: self.prepare_guide(a)).pack(anchor="w", pady=(S3, 0))
        ui.Callout(tear, kind="warning", wraplength=900,
                   text="Può interrompere accesso remoto, Hyper-V/WSL e connessioni attive: esegui queste "
                        "operazioni dal PC in locale.").pack(fill="x")
        self.show_mode("setup")
        self.validate_form()

    def show_mode(self, key):
        for k, frame in self.modes.items():
            frame.pack_forget()
            self.seg_buttons[k].configure(style="SegActive.TButton" if k == key else "Seg.TButton")
        self.modes[key].pack(fill="both", expand=True)
        self.update_scope()

    # ---- WAN rows (1..N, bounded by the adapters on this PC) ----
    def adapter_names(self):
        return [ad["Name"] for ad in (self.data or {}).get("adapters", [])]

    def default_route_aliases(self):
        return [r.get("InterfaceAlias") for r in self.default_routes()]

    def free_wan_candidates(self, exclude_row=None):
        used = {self.lan.get()} | {r["alias"].get() for r in self.wan_rows if r is not exclude_row}
        names = [n for n in self.adapter_names() if n not in used]
        online = [n for n in self.default_route_aliases() if n in names]
        return online + [n for n in names if n not in online]

    def add_wan_row(self, alias=None, metric=None, validate=True):
        if alias is None:
            free = self.free_wan_candidates()
            if self.data is not None and not free:
                return
            alias = free[0] if free else ""
        if metric is None:
            metric = str(network_guide.suggest_metric(
                [{"alias": r["alias"].get(), "metric": r["metric"].get()} for r in self.wan_rows]))
        row = {"alias": tk.StringVar(value=alias), "metric": tk.StringVar(value=metric)}
        self.wan_rows.append(row)
        for var in (row["alias"], row["metric"]):
            var.trace_add("write", lambda *a: self.validate_form())
        self.layout_wan_rows()
        if validate:
            self.validate_form()

    def remove_wan_row(self, row):
        if len(self.wan_rows) > 1:
            self.wan_rows.remove(row)
            self.layout_wan_rows()
            self.validate_form()

    def move_wan_row(self, row, delta):
        i = self.wan_rows.index(row)
        j = i + delta
        if 0 <= j < len(self.wan_rows):
            self.wan_rows[i], self.wan_rows[j] = self.wan_rows[j], self.wan_rows[i]
            # Keep metrics in priority order: swap the values along with the rows.
            mi, mj = self.wan_rows[i]["metric"].get(), self.wan_rows[j]["metric"].get()
            self.wan_rows[i]["metric"].set(mj)
            self.wan_rows[j]["metric"].set(mi)
            self.layout_wan_rows()
            self.validate_form()

    def layout_wan_rows(self):
        for child in self.wan_frame.winfo_children():
            child.destroy()
        for key in [k for k in self.field_errors if ":" in k]:
            del self.field_errors[key]
            del self.field_widgets[key]
        single = len(self.wan_rows) == 1
        for i, row in enumerate(self.wan_rows):
            r = i * 2
            tk.Label(self.wan_frame, text=str(i + 1), font=F["overline"], width=2,
                     bg=C["info"] if i == 0 else C["surface_alt"],
                     fg="#FFFFFF" if i == 0 else C["text_muted"]).grid(row=r, column=0, sticky="w", padx=(0, S2))
            combo = ttk.Combobox(self.wan_frame, textvariable=row["alias"], state="readonly")
            combo.grid(row=r, column=1, sticky="ew")
            combo.configure(postcommand=lambda row=row, combo=combo: combo.configure(
                values=self.free_wan_candidates(exclude_row=row)))
            combo["values"] = self.free_wan_candidates(exclude_row=row)
            entry = ttk.Entry(self.wan_frame, textvariable=row["metric"], width=6, justify="center")
            entry.grid(row=r, column=2, padx=(S2, 0))
            tools = tk.Frame(self.wan_frame, bg=C["surface"])
            tools.grid(row=r, column=3, padx=(S1, 0))
            up = ttk.Button(tools, text="\u2191", width=2, style="CardGhost.TButton",
                            command=lambda row=row: self.move_wan_row(row, -1))
            up.pack(side="left")
            if i == 0:
                up.state(["disabled"])
            remove = ttk.Button(tools, text="\u2715", width=2, style="CardGhost.TButton",
                                command=lambda row=row: self.remove_wan_row(row))
            remove.pack(side="left")
            if single:
                remove.state(["disabled"])
            hint = ("Primaria \u00b7 deve essere gi\u00e0 connessa a Internet" if i == 0
                    else "Riserva \u00b7 subentra se cadono le WAN sopra")
            msg = ttk.Label(self.wan_frame, text=hint, style="Card.Caption.TLabel")
            msg.grid(row=r + 1, column=1, columnspan=3, sticky="w", pady=(2, S2))
            self.field_errors["wan:%d" % i] = (msg, hint)
            self.field_widgets["wan:%d" % i] = combo
            self.field_errors["metric:%d" % i] = (msg, hint)
            self.field_widgets["metric:%d" % i] = entry
        self.update_add_wan()

    def update_add_wan(self):
        if not hasattr(self, "add_wan_button"):
            return
        free = self.free_wan_candidates() if self.data is not None else ["?"]
        self.add_wan_button.state(["!disabled"] if free else ["disabled"])
        total = len(self.adapter_names())
        self.add_wan_hint.configure(
            text="" if free else "Tutte le interfacce disponibili sono gi\u00e0 in uso" if total
            else "")

    def on_lan_changed(self):
        """Selecting a LAN adopts the subnet already on that adapter, else 10.10.10.0/24."""
        if self.data is None or not hasattr(self, "subnet_badge"):
            return
        lan = self.lan.get()
        clash = [r for r in self.wan_rows if r["alias"].get() == lan]
        for row in clash:   # an adapter cannot be LAN and WAN: the LAN choice wins
            if len(self.wan_rows) > 1:
                self.wan_rows.remove(row)
            else:
                free = self.free_wan_candidates(exclude_row=row)
                row["alias"].set(free[0] if free else "")
        if clash:
            self.layout_wan_rows()
            self.toast.show(lan + " ora \u00e8 la LAN: rimossa dalle WAN.", "info")
        if lan != self.subnet_detected_for:
            self.subnet_detected_for = lan
            self.apply_detected_subnet()
        self.update_add_wan()
        self.render_secondary_ips()

    def render_secondary_ips(self):
        if not hasattr(self, "secondary_table"):
            return
        self.secondary_table.delete(*self.secondary_table.get_children())
        self.secondary_rows = {}
        lan = self.lan.get()
        for row in secondary_ips.lan_rows(self.data or {}, lan):
            secondary = secondary_ips.skip_as_source(row.get("SkipAsSource"))
            state = "Secondario" if secondary else "Sorgente / protetto"
            ip, prefix = row["IPAddress"], int(row["PrefixLength"])
            for pending in self.pending:
                if pending["kind"] != "lan_ip":
                    continue
                action, alias, target, bits, old, old_bits, _index = pending["args"]
                if alias != lan:
                    continue
                if action == "remove" and (ip, prefix) == (target, bits):
                    state += " · rimozione in attesa"
                if action == "edit" and (ip, prefix) == (old, old_bits):
                    state += " · modifica in attesa"
            item = self.secondary_table.insert("", "end", values=(ip, "/" + str(prefix), state))
            self.secondary_rows[item] = row
        for pending in self.pending:
            if pending["kind"] != "lan_ip":
                continue
            action, alias, ip, bits, _old, _old_bits, _index = pending["args"]
            if alias == lan and action in ("add", "edit"):
                self.secondary_table.insert("", "end",
                                            values=(ip, "/" + str(bits), "＋ Da aggiungere · in attesa"))
        self.secondary_selected()

    def secondary_selected(self, _event=None):
        selected = self.secondary_table.selection()
        row = self.secondary_rows.get(selected[0]) if selected else None
        editable = bool(row and secondary_ips.skip_as_source(row.get("SkipAsSource")))
        self.secondary_edit_button.configure(state="normal" if editable else "disabled")
        self.secondary_remove_button.configure(state="normal" if editable else "disabled")

    def prepare_secondary(self, action):
        if not self.data:
            return self.toast.show("Aggiorna prima lo stato della rete.", "warning")
        if self.tasks:
            return self.toast.show("Attendi il completamento dell'operazione corrente.", "warning")
        selected = self.secondary_table.selection()
        old = self.secondary_rows.get(selected[0]) if selected else None
        if action in ("edit", "remove") and not (
                old and secondary_ips.skip_as_source(old.get("SkipAsSource"))):
            return self.toast.show("Seleziona un IPv4 secondario, non l'IP sorgente.", "warning")
        alias = self.lan.get()
        old_ip = old["IPAddress"] if action == "edit" else None
        old_prefix = int(old["PrefixLength"]) if action == "edit" else None
        if action == "remove":
            ip, bits = old["IPAddress"], int(old["PrefixLength"])
            try:
                plan = secondary_ips.plan(action, alias, ip, bits, self.data)
            except ValueError as exc:
                return messagebox.showwarning("IPv4 secondario", str(exc))
            dlg = Dialog(self, "Rimuovere IPv4 secondario?", "Prepara rimozione", kind="Danger")
            ttk.Label(dlg.body,
                      text="LAN: " + alias + "\nIPv4: " + ip + "/" + str(bits)
                           + "\nL'indirizzo principale rimarrà invariato.",
                      style="Card.TLabel", justify="left").pack(anchor="w")
            if not dlg.run():
                return
        else:
            dlg = Dialog(self, ("Aggiungi" if action == "add" else "Modifica") +
                         " IPv4 secondario", "Prepara modifica")
            ip_var = tk.StringVar(value=old["IPAddress"] if old else "")
            prefix_var = tk.StringVar(value=str(old["PrefixLength"]) if old else "24")
            ttk.Label(dlg.body, text="Interfaccia LAN: " + alias,
                      style="Card.Strong.TLabel").pack(anchor="w", pady=(0, S3))
            ttk.Label(dlg.body, text="Indirizzo IPv4", style="Card.TLabel").pack(anchor="w")
            ip_entry = ttk.Entry(dlg.body, textvariable=ip_var, width=38)
            ip_entry.pack(fill="x", pady=(S1, S2))
            ttk.Label(dlg.body, text="Prefisso CIDR (1–32)",
                      style="Card.TLabel").pack(anchor="w")
            ttk.Entry(dlg.body, textvariable=prefix_var).pack(fill="x", pady=(S1, S2))
            ttk.Label(dlg.body, text="SkipAsSource attivo · Nessun gateway aggiuntivo",
                      style="Card.Caption.TLabel").pack(anchor="w")
            err_label = ttk.Label(dlg.body, text="", style="Card.Error.TLabel",
                                  wraplength=420, justify="left")
            err_label.pack(fill="x", pady=(S2, S1))
            plan_holder = [None]

            def check(*_):
                try:
                    plan_holder[0] = secondary_ips.plan(
                        action, alias, ip_var.get(), prefix_var.get(), self.data,
                        old_address=old_ip, old_prefix=old_prefix)
                    err_label.configure(text="")
                except ValueError as exc:
                    plan_holder[0] = None
                    err_label.configure(text=friendly_ip_error(exc, "10.10.20.1/24"))
                dlg.ok.configure(state="normal" if plan_holder[0] else "disabled")
            ip_var.trace_add("write", check)
            prefix_var.trace_add("write", check)
            check()
            if not dlg.run(focus=ip_entry):
                return
            plan = plan_holder[0]
            if plan is None:
                return
        args = (action, alias, plan["ip"], plan["prefix"],
                plan["old_ip"], plan["old_prefix"], plan["index"])
        labels = {"add": "Aggiungi Secondary IP", "edit": "Modifica Secondary IP",
                  "remove": "Rimuovi Secondary IP"}
        description = alias + " · " + plan["ip"] + "/" + str(plan["prefix"])
        if action == "edit":
            description = (alias + " · " + str(plan["old_ip"]) + "/" +
                           str(plan["old_prefix"]) + " → " +
                           plan["ip"] + "/" + str(plan["prefix"]))
        description += ("\nNessuna modifica manuale a gateway, route statiche o WinNAT. "
                        "Le route connesse possono cambiare automaticamente.")
        self.stage("lan_ip", args, labels[action], description)
        self.show_page("changes")

    def follow_prefix(self):
        """Typing a new subnet moves the PC address to its first host if it no longer fits."""
        try:
            subnet = ipaddress.IPv4Network(network.validate_prefix(self.prefix.get().strip()))
            ip = ipaddress.IPv4Address(self.gateway.get().strip())
            if ip in subnet and ip not in (subnet.network_address, subnet.broadcast_address):
                return
        except ValueError:
            try:
                subnet = ipaddress.IPv4Network(network.validate_prefix(self.prefix.get().strip()))
            except ValueError:
                return
        self.gateway.set(str(next(subnet.hosts())))

    def apply_detected_subnet(self):
        found = network_guide.detect_lan_subnet(self.data or {}, self.lan.get())
        self.prefix.set(found["prefix"])
        self.gateway.set(found["gateway"])
        self.subnet_source = found
        self.show_subnet_source()

    def show_subnet_source(self):
        found = getattr(self, "subnet_source", None)
        if not found:
            self.subnet_badge.grid_remove()
            return
        self.subnet_badge.grid()
        lan = self.lan.get()
        modified = (found["prefix"] != self.prefix.get().strip()
                    or found["gateway"] != self.gateway.get().strip())
        if found.get("origin") == "Dhcp":
            self.subnet_badge.set("IP STATICO PERSONALIZZATO" if modified else "DHCP → STATICO", "accent")
            text = (lan + " usa DHCP: al Commit verrà disabilitato e verrà configurato "
                    + self.gateway.get().strip() + " su " + self.prefix.get().strip()
                    + ". L'IP ricevuto via DHCP non viene importato; puoi modificare i valori.")
        elif modified:
            self.subnet_badge.set("MODIFICATA A MANO", "accent")
            text = ("Valori personalizzati. Rilevati su " + lan + ": " + found["gateway"] + " in " + found["prefix"]
                    if found["source"] == "rilevata" else "Valori personalizzati al posto di quelli predefiniti.")
        elif found["source"] == "rilevata":
            self.subnet_badge.set("RILEVATA SU " + lan.upper(), "success")
            text = "Indirizzamento LAN statico esistente conservato; il NAT usa la subnet selezionata."
        else:
            self.subnet_badge.set("PREDEFINITA", "neutral")
            text = lan + " non ha un IPv4 utilizzabile: verrà configurata la subnet predefinita."
        self.subnet_hint.configure(text=text)

    def reset_form(self):
        d = network_guide.DEFAULTS
        names = self.adapter_names()
        if not names or d["lan"] in names:
            self.lan.set(d["lan"])
        self.wan_rows.clear()
        online = [n for n in self.default_route_aliases() if n != self.lan.get()]
        first = online[0] if online else d["wans"][0]["alias"]
        self.add_wan_row(first, str(d["wans"][0]["metric"]), validate=False)
        self.profile_nat.set(d["nat"])
        self.subnet_detected_for = None
        if self.data is not None:
            self.on_lan_changed()
        else:
            self.prefix.set(d["prefix"])
            self.gateway.set(d["gateway"])
        self.validate_form()

    def form_profile(self):
        return {"lan": self.lan.get(),
                "wans": [{"alias": r["alias"].get(), "metric": r["metric"].get().strip()} for r in self.wan_rows],
                "prefix": self.prefix.get().strip(), "gateway": self.gateway.get().strip(),
                "nat": self.profile_nat.get().strip()}

    def field_problems(self):
        """Inline, per-field validation (error prevention before any PowerShell call)."""
        p, errors = self.form_profile(), {}
        if not p["lan"]:
            errors["lan"] = "Seleziona la scheda LAN."
        seen = {p["lan"]}
        previous = 0
        for i, w in enumerate(p["wans"]):
            if not w["alias"]:
                errors["wan:%d" % i] = "Seleziona un'interfaccia."
            elif w["alias"] in seen:
                errors["wan:%d" % i] = ("Deve essere diversa dalla LAN." if w["alias"] == p["lan"]
                                        else "Interfaccia gi\u00e0 usata da un'altra WAN.")
            seen.add(w["alias"])
            try:
                metric = int(w["metric"])
                if not 1 <= metric <= 9999:
                    raise ValueError
            except ValueError:
                errors["metric:%d" % i] = "Metrica: numero intero da 1 a 9999."
                continue
            if metric <= previous:
                errors["metric:%d" % i] = "Metrica: deve essere maggiore di " + str(previous) + " (WAN sopra)."
            previous = metric
        subnet = None
        try:
            subnet = ipaddress.IPv4Network(network.validate_prefix(p["prefix"]))
        except ValueError as exc:
            errors["prefix"] = friendly_ip_error(exc, "10.10.10.0/24")
        if subnet is not None:
            try:
                network.validate_gateway(p["gateway"], subnet)
            except ValueError as exc:
                errors["gateway"] = friendly_ip_error(exc, str(next(subnet.hosts(), "10.10.10.1")))
            for alias, net in network_guide.wan_networks(self.data or {}, [w["alias"] for w in p["wans"]]):
                if net.overlaps(subnet):
                    errors["prefix"] = "Si sovrappone alla rete di " + alias + " (" + str(net) + ")."
        try:
            network.validate_name(p["nat"])
        except ValueError as exc:
            errors["nat"] = str(exc)
        return errors

    def plan_wrap_width(self, width=None):
        """Text width for a plan step: list width minus the step number and padding."""
        width = width or self.plan_list.winfo_width()
        return max(160, width - 56) if width > 1 else 380

    def validate_form(self):
        if not hasattr(self, "plan_list"):
            return
        errors = self.field_problems()
        shown = set()
        for key, (label, hint) in self.field_errors.items():
            err = errors.get(key)
            if ":" in key:  # WAN rows share one message line for alias + metric
                index = key.split(":")[1]
                err = errors.get("wan:" + index) or errors.get("metric:" + index)
            if id(label) not in shown or err:
                label.configure(text="⚠  " + err if err else hint,
                                style="Card.Error.TLabel" if err else "Card.Caption.TLabel")
                shown.add(id(label))
            widget = self.field_widgets[key]
            if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
                widget.configure(style="Invalid.TEntry" if errors.get(key) else "TEntry")
        if hasattr(self, "subnet_badge"):
            self.show_subnet_source()
            self.update_add_wan()
        self.plan_labels = []
        for child in self.plan_list.winfo_children():
            child.destroy()
        issue = None
        lines = []
        if self.data is None:
            issue = "Attendi il caricamento della configurazione di rete…"
        elif errors:
            issue = "Da correggere: " + ", ".join(field_title(k) for k in errors) + "."
        else:
            try:
                lines = network_guide.preview("apply", self.form_profile(), self.data)
            except Exception as exc:
                issue = str(exc)
        for i, line in enumerate(l for l in lines if not l.startswith("ATTENZIONE")):
            r = tk.Frame(self.plan_list, bg=C["surface"])
            r.pack(fill="x", pady=1)
            tk.Label(r, text=str(i + 1), font=F["overline"], width=3, bg=C["surface_alt"], fg=C["text_muted"]).pack(side="left", anchor="n", pady=2)
            # Wrap from the list width (known up front) rather than from each
            # label's own size: no wrap -> resize -> rewrap feedback loop.
            t = tk.Label(r, text=line, font=F["body"], bg=C["surface"], fg=C["text"], anchor="w", justify="left",
                         wraplength=self.plan_wrap_width())
            t.pack(side="left", fill="x", expand=True, padx=S2)
            self.plan_labels.append(t)
        if issue:
            self.setup_issue.set(issue, "info" if self.data is None or errors else "danger")
            self.setup_issue.pack(fill="x", pady=(S2, S3), before=self.plan_list)
        else:
            self.setup_issue.pack_forget()
        self.prepare_button.configure(state="disabled" if issue else "normal")
        self.topology.errors = errors
        self.topology.draw()
        self.update_scope()

    def update_scope(self):
        if not hasattr(self, "scope_label"):
            return
        wans = ", ".join(r["alias"].get() for r in self.wan_rows if r["alias"].get()) or "—"
        self.scope_label.set("Interfacce interessate (dalla scheda Configura):  LAN " + (self.lan.get() or "—")
                             + "   ·   WAN " + wans, "info")

    # ---------------------------------------------------------- changes ---
    def build_changes(self, page):
        ttk.Button(page.actions, text="Scarta tutto", command=self.discard).pack(side="right")
        self.changes_box = ttk.Frame(page)
        self.changes_box.pack(fill="both", expand=True)
        console_card = ui.Card(page, padding=S3)
        console_card.pack(fill="both", expand=True, pady=(S2, 0))
        console_header = tk.Frame(console_card.body, bg=C["surface"])
        console_header.pack(fill="x")
        tk.Label(console_header, text="Console Commit · PowerShell", font=F["strong"],
                 fg=C["text"], bg=C["surface"]).pack(side="left")
        ttk.Button(console_header, text="Copia output", command=self.copy_commit_log).pack(side="right")
        ttk.Button(console_header, text="Pulisci", command=self.clear_commit_log).pack(side="right", padx=S2)
        console_frame = tk.Frame(console_card.body, bg=C["surface_alt"])
        console_frame.pack(fill="both", expand=True, pady=(S2, 0))
        self.commit_console = tk.Text(console_frame, wrap="none", height=13,
                                      font=F["mono_s"], state="disabled",
                                      bg=C["surface_alt"], fg=C["text"], bd=0,
                                      insertbackground=C["text"], padx=S2, pady=S2,
                                      selectbackground=C["select"])
        yscroll = ttk.Scrollbar(console_frame, orient="vertical", command=self.commit_console.yview)
        xscroll = ttk.Scrollbar(console_frame, orient="horizontal", command=self.commit_console.xview)
        self.commit_console.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.commit_console.pack(side="left", fill="both", expand=True)
        self.commit_console.bind("<Control-a>", lambda e: (self.commit_console.tag_add("sel", "1.0", "end-1c"), "break")[1])
        self.commit_console.tag_configure("command", foreground=C["accent"])
        self.commit_console.tag_configure("stderr", foreground=C["danger"])
        self.commit_console.tag_configure("status", foreground=C["text_muted"])
        self.commit_console.tag_configure("info", foreground=C["text_muted"])
        # Kept for compatibility with older code paths (select + unstage).
        self.pending_table = ttk.Treeview(page, columns=("action", "details"), show="headings")
        self.summary = tk.Text(page)

    def append_commit_log(self, kind, message):
        """Only the Tk event-loop may edit the read-only Commit console."""
        if not hasattr(self, "commit_console"):
            return
        prefix = {"command": ">>> PowerShell", "stdout": "STDOUT", "stderr": "STDERR",
                  "status": "ESITO", "info": "COMMIT"}.get(kind, kind.upper())
        text = prefix + ":\n" + str(message).rstrip() + "\n\n"
        widget = self.commit_console
        widget.configure(state="normal")
        widget.insert("end", text, kind)
        widget.configure(state="disabled")
        widget.see("end")

    def clear_commit_log(self):
        if "Commit" in self.tasks:
            return
        self.commit_console.configure(state="normal")
        self.commit_console.delete("1.0", "end")
        self.commit_console.configure(state="disabled")

    def copy_commit_log(self):
        details = self.commit_console.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(details)
        self.update_idletasks()
        self.toast.show("Output dei comandi copiato.", "success")

    def render_changes(self):
        for child in self.changes_box.winfo_children():
            child.destroy()
        if not self.pending:
            empty = ui.Card(self.changes_box, padding=S5 * 2)
            empty.pack(fill="x")
            tk.Label(empty.body, text=ui.icon("ok"), font=F["icon_l"], bg=C["surface"], fg=C["success"]).pack()
            tk.Label(empty.body, text="Nessuna modifica in attesa", font=F["strong"], bg=C["surface"], fg=C["text"]).pack(pady=(S2, 0))
            tk.Label(empty.body, text="La configurazione di Windows non verrà alterata. Prepara un'operazione da Gateway o Regole NAT.",
                     font=F["body"], bg=C["surface"], fg=C["text_muted"]).pack(pady=(S1, 0))
            return
        if len(self.pending) > 1:
            ui.Callout(self.changes_box, kind="warning", wraplength=900,
                       text="Windows non offre rollback atomico: applica una modifica per volta. "
                            "Rimuovi quelle che non servono adesso.").pack(fill="x", pady=(0, S3))
        for i, p in enumerate(self.pending):
            destructive = p["kind"] in ("remove", "reset", "teardown", "external_teardown") or \
                (p["kind"] == "guide" and p["args"][0] in ("disable", "reset"))
            card = ui.Card(self.changes_box, edge=C["danger"] if destructive else C["accent"], padding=S4)
            card.pack(fill="x", pady=(0, S3))
            head = tk.Frame(card.body, bg=C["surface"])
            head.pack(fill="x")
            tk.Label(head, text=str(i + 1), font=F["body_b"], width=3, bg=C["accent_soft"], fg=C["accent"]).pack(side="left")
            tk.Label(head, text=p["label"], font=F["strong"], bg=C["surface"], fg=C["text"]).pack(side="left", padx=S2)
            ui.Badge(head, "DISTRUTTIVA" if destructive else "IN ATTESA",
                     "danger" if destructive else "warning").pack(side="left", padx=S2)
            ttk.Button(head, text="Rimuovi", style="CardGhost.TButton",
                       command=lambda n=i: self.unstage(n)).pack(side="right")
            for line in str(p["details"]).split("\n"):
                warn = line.startswith("ATTENZIONE")
                tk.Label(card.body, text=("⚠  " if warn else "•  ") + line, font=F["body"], bg=C["surface"],
                         fg=C["warning"] if warn else C["text_muted"], anchor="w", justify="left",
                         wraplength=860).pack(anchor="w", pady=(S1, 0), padx=(28, 0))

    # --------------------------------------------------------- sessions ---
    def build_sessions(self, page):
        ttk.Button(page.actions, text="Aggiorna", command=self.refresh_sessions).pack(side="right")
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, S3))
        self.session_filter = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.session_filter, width=40)
        entry.pack(side="left")
        self.session_filter.trace_add("write", lambda *a: self.show_sessions(self.session_rows))
        ttk.Label(bar, text="  Filtra per IP, porta, protocollo o NAT", style="Caption.TLabel").pack(side="left")
        self.session_status = tk.StringVar(value="Apri la scheda per caricare le sessioni.")
        ttk.Label(bar, textvariable=self.session_status, style="Muted.TLabel").pack(side="right")
        wrap, self.session_table = ui.make_table(page, [("nat", "NAT", 150), ("proto", "Protocollo", 100),
            ("src", "Origine interna", 220), ("dst", "Destinazione", 220), ("external", "Tradotta come", 220)], height=16)
        wrap.pack(fill="both", expand=True)
        ttk.Label(page, text="Aggiornamento automatico ogni 60 s mentre la scheda è aperta · massimo 500 righe.",
                  style="Caption.TLabel").pack(anchor="w", pady=(S2, 0))
        self.session_entry = entry

    # ------------------------------------------------------------ about ---
    def build_about(self, page):
        card = ui.Card(page, padding=S5)
        card.pack(fill="x")
        tk.Label(card.body, text="WinNAT UI " + VERSION, font=F["title"], bg=C["surface"], fg=C["text"]).pack(anchor="w")
        tk.Label(card.body, text="Autore: Matteo Cannizzo · Licenza MIT", font=F["body"], bg=C["surface"],
                 fg=C["text_muted"]).pack(anchor="w", pady=(S1, 0))
        link = tk.Label(card.body, text=REPO_URL.replace("https://", ""), font=F["body"], bg=C["surface"],
                        fg=C["accent"], cursor="hand2")
        link.pack(anchor="w", pady=(S2, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))
        tk.Label(card.body, text="I metadati dell'autore non equivalgono a una firma digitale: l'eseguibile non è firmato.",
                 font=F["caption"], bg=C["surface"], fg=C["text_muted"]).pack(anchor="w", pady=(S3, 0))
        updates = ui.Card(page, padding=S4)
        updates.pack(fill="x", pady=(S3, 0))
        tk.Label(updates.body, text="Aggiornamenti da GitHub", font=F["strong"],
                 bg=C["surface"], fg=C["text"]).pack(anchor="w")
        tk.Label(updates.body, text="Verifica la release stabile ufficiale, scarica e verifica SHA256. "
                 "L'installazione avviene dopo la chiusura, conservando un backup dei file precedenti.",
                 wraplength=600, justify="left", font=F["body"],
                 bg=C["surface"], fg=C["text_muted"]).pack(anchor="w", pady=(S1, S2))
        ttk.Button(updates.body, text="Controlla aggiornamenti",
                   command=self.check_updates).pack(anchor="w")
        issues = ui.Card(page, padding=S4)
        issues.pack(fill="x", pady=(S3, 0))
        heading = tk.Frame(issues.body, bg=C["surface"])
        heading.pack(fill="x")
        tk.Label(heading, text="Bug segnalati e correzioni", font=F["strong"],
                 bg=C["surface"], fg=C["text"]).pack(side="left")
        ttk.Button(heading, text="Verifica stato Issue", command=self.refresh_issue_tracker).pack(side="right")
        ttk.Button(heading, text="Segui Issue GitHub", command=self.follow_github_issue).pack(side="right", padx=(0, S2))
        ttk.Button(heading, text="Nuova segnalazione", command=self.create_manual_issue).pack(side="right", padx=(0, S2))
        self.issue_status = tk.StringVar(value="Archivio locale delle segnalazioni.")
        tk.Label(issues.body, textvariable=self.issue_status, bg=C["surface"],
                 fg=C["text_muted"], font=F["caption"]).pack(anchor="w", pady=(S2, 0))
        self.issue_query = tk.StringVar()
        controls = tk.Frame(issues.body, bg=C["surface"])
        controls.pack(fill="x", pady=(S2, 0))
        tk.Label(controls, text="Cerca per titolo o ID:", bg=C["surface"],
                 fg=C["text"]).pack(side="left")
        ttk.Entry(controls, textvariable=self.issue_query, width=28).pack(side="left", padx=S2)
        self.issue_query.trace_add("write", lambda *_: self.render_issue_tracker())
        self.issue_filter = tk.StringVar(value="Tutti")
        filters = ttk.Combobox(controls, textvariable=self.issue_filter, state="readonly",
                               values=("Tutti", "Aperti", "Chiusi", "Correzione disponibile"), width=23)
        filters.pack(side="left", padx=S2)
        filters.bind("<<ComboboxSelected>>", lambda _e: self.render_issue_tracker())
        self.issue_table = ttk.Treeview(issues.body,
                                        columns=("number","title","state","priority","fix"),
                                        show="headings", height=6)
        for field, label, width in (("number","Issue",65), ("title","Problema",360),
                                    ("state","Stato",145), ("priority","Priorità",85),
                                    ("fix","Correzione",150)):
            self.issue_table.heading(field, text=label)
            self.issue_table.column(field, width=width)
        self.issue_table.pack(fill="x", pady=(S2, 0))
        self.issue_table.bind("<Double-1>", self.open_tracked_issue)
        self.issue_table.bind("<<TreeviewSelect>>", self.show_tracked_issue_details)
        ttk.Button(issues.body, text="Aggiungi informazioni su GitHub",
                   command=self.add_issue_information).pack(anchor="w", pady=(S2, 0))
        self.issue_details = tk.StringVar(value="Seleziona una segnalazione per visualizzarne i dettagli.")
        tk.Label(issues.body, textvariable=self.issue_details, bg=C["surface"],
                 fg=C["text_muted"], font=F["caption"], justify="left",
                 anchor="w", wraplength=750).pack(fill="x", pady=(S2, 0))
        self.render_issue_tracker()
        self.section(page, "Scorciatoie da tastiera")
        keys = ui.Card(page, padding=S4)
        keys.pack(fill="x")
        for i, (k, v) in enumerate([("F5", "Aggiorna configurazione"), ("Ctrl + 1 … 6", "Cambia sezione"),
                                    ("Ctrl + Invio", "Applica la modifica in attesa"), ("Canc", "Elimina la regola NAT selezionata"),
                                    ("Ctrl + F", "Filtra le sessioni"), ("Esc", "Chiude le finestre di dialogo")]):
            tk.Label(keys.body, text=k, font=F["mono_s"], bg=C["surface_alt"], fg=C["text"], padx=S2, pady=2).grid(
                row=i, column=0, sticky="w", pady=2)
            tk.Label(keys.body, text=v, font=F["body"], bg=C["surface"], fg=C["text_muted"]).grid(row=i, column=1, sticky="w", padx=S4)

    def create_manual_issue(self):
        """Report an externally observed problem without fabricating an exception."""
        dlg = Dialog(self, "Nuova segnalazione", "Pubblica su GitHub")
        tk.Label(dlg.body, text="Segnala un problema anche senza errori di WinNAT-UI.",
                 bg=C["surface"], fg=C["text_muted"], font=F["body"]).pack(anchor="w")
        tk.Label(dlg.body, text="Titolo del problema", bg=C["surface"], fg=C["text"],
                 font=F["strong"]).pack(anchor="w", pady=(S3, S1))
        subject = tk.StringVar()
        title_input = ttk.Entry(dlg.body, textvariable=subject, width=73)
        title_input.pack(fill="x")
        tk.Label(dlg.body, text="Tipo di problema", bg=C["surface"], fg=C["text"],
                 font=F["strong"]).pack(anchor="w", pady=(S3, S1))
        kind = tk.StringVar(value="Problema esterno")
        ttk.Combobox(dlg.body, textvariable=kind, state="readonly", width=34,
                     values=("Problema esterno", "Incompatibilita",
                             "Comportamento inatteso", "Altro problema")).pack(anchor="w")
        tk.Label(dlg.body, text="Descrizione, condizioni, risultati osservati e risultato atteso",
                 bg=C["surface"], fg=C["text"], font=F["strong"]).pack(anchor="w", pady=(S3, S1))
        description = tk.Text(dlg.body, height=9, width=75, wrap="word",
                              bg=C["surface_alt"], fg=C["text"], insertbackground=C["text"],
                              selectbackground=C["select"], selectforeground=C["text"])
        description.pack(fill="both", expand=True)
        include_inventory = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg.body, text="Allega inventario rete disponibile (IP, interfacce e topologia)",
                        variable=include_inventory).pack(anchor="w", pady=(S3, S1))
        tk.Label(dlg.body,
                 text="La Issue sarà PUBBLICA. Verranno aggiunti versione e ambiente del PC. "
                      "Nessun traceback è richiesto. Controlla i dati prima di inviare.",
                 bg=C["surface"], fg=C["text_muted"], font=F["caption"],
                 wraplength=590, justify="left").pack(anchor="w", pady=(S2, 0))

        def build():
            return issue_tracker.manual_payload(
                subject.get(), description.get("1.0", "end-1c"), kind.get(), VERSION,
                inventory=self.data if include_inventory.get() else None,
                is_admin=self.is_admin)

        def preview():
            try:
                payload = build()
            except ValueError as exc:
                messagebox.showwarning("Dati mancanti", str(exc), parent=dlg)
                return
            title, body = bug_report.format_report(payload)
            viewer = Dialog(self, "Anteprima della Issue pubblica", "Chiudi")
            viewer.cancel_btn.pack_forget()
            content = tk.Text(viewer.body, height=21, width=94, wrap="word",
                              font=F["mono_s"], bg=C["surface_alt"], fg=C["text"],
                              selectbackground=C["select"], selectforeground=C["text"])
            content.pack(fill="both", expand=True)
            content.insert("1.0", title + "\n\n" + body)
            content.configure(state="disabled")
            viewer.resizable(True, True)
            viewer.run(focus=viewer.ok)

        ttk.Button(dlg.body, text="Anteprima dati da pubblicare",
                   command=preview).pack(anchor="w", pady=(S2, 0))

        def publish():
            if "Segnala bug" in self.tasks:
                return
            try:
                payload = build()
            except ValueError as exc:
                messagebox.showwarning("Dati mancanti", str(exc), parent=dlg)
                return
            if not messagebox.askyesno(
                    "Conferma pubblicazione",
                    "Stai per aprire o aggiornare una Issue GitHub pubblica.\n\n"
                    "Il testo e le informazioni di sistema saranno pubblici; l'inventario rete "
                    "sarà incluso solo se selezionato. La mascheratura dei segreti non è infallibile.\n\n"
                    "Hai verificato l'anteprima e confermi l'invio?", parent=dlg):
                return
            progress = ProgressDialog(dlg, "Invio segnalazione", "Invio su GitHub in corso…")

            def send():
                result = issue_tracker.submit(payload)
                issue_tracker.save_entry(payload, result)
                return result

            def sent(result):
                self.render_issue_tracker()
                self.notice.set("Issue #" + str(result["number"]) + " collegata.")
                progress.succeed("Segnalazione inviata",
                                 "Issue #" + str(result["number"]) +
                                 (" aggiornata." if result["already_exists"] else " creata.") +
                                 " Monitoraggio attivato.",
                                 url=result["url"], on_close=dlg.destroy)

            def failed(message):
                progress.fail("Segnalazione non inviata",
                              "Il servizio remoto non è disponibile. Nessuna nuova eccezione applicativa "
                              "è stata generata.\n" + message,
                              retry=publish)

            self.run_task("Segnala bug", send, sent, on_error=failed)

        dlg.ok.configure(command=publish)
        dlg.resizable(True, True)
        dlg.run(focus=title_input)

    def follow_github_issue(self):
        """Subscribe to a GitHub Issue already created outside the application."""
        reference = simpledialog.askstring(
            "Segui Issue GitHub", "Inserisci il numero (es. #76) o l'URL della Issue WinNAT-UI:",
            parent=self)
        if reference is None:
            return
        try:
            number = issue_tracker.issue_number(reference)
        except ValueError as exc:
            messagebox.showwarning("Issue non valida", str(exc), parent=self)
            return
        if "Segui Issue" in self.tasks:
            return
        progress = ProgressDialog(self, "Collegamento Issue", "Verifica della Issue GitHub…")

        def link():
            return issue_tracker.track_issue(number)

        def completed(result):
            record, added = result
            self.render_issue_tracker()
            for iid in self.issue_table.get_children():
                if self.issue_table.set(iid, "number") == "#" + str(record["number"]):
                    self.issue_table.selection_set(iid)
                    self.issue_table.see(iid)
                    self.show_tracked_issue_details()
                    break
            progress.succeed("Issue collegata" if added else "Issue già seguita",
                             "#" + str(record["number"]) +
                             " è disponibile nella sezione Informazioni.",
                             url=record["url"])

        def failed(message):
            progress.fail("Collegamento non riuscito",
                          "Impossibile verificare la Issue GitHub.\n" + message,
                          retry=self.follow_github_issue)

        self.run_task("Segui Issue", link, completed, on_error=failed)

    def add_issue_information(self):
        """Use authenticated GitHub comments without shipping a write token."""
        selected = self.issue_table.selection()
        if not selected:
            messagebox.showinfo("Seleziona una Issue",
                                "Seleziona una segnalazione da aggiornare.", parent=self)
            return
        entries = issue_tracker.history()
        index = int(selected[0])
        if index < len(entries):
            webbrowser.open(entries[index]["url"])

    def render_issue_tracker(self):
        if not hasattr(self, "issue_table"):
            return
        self.issue_table.delete(*self.issue_table.get_children())
        entries = issue_tracker.history()
        query = self.issue_query.get().strip().casefold() if hasattr(self, "issue_query") else ""
        issue_filter = self.issue_filter.get() if hasattr(self, "issue_filter") else "Tutti"
        status_names = {"ricevuto": "Ricevuto", "in-analisi": "In analisi",
                        "informazioni-richieste": "Informazioni richieste",
                        "confermato": "Confermato", "in-correzione": "In correzione",
                        "correzione-disponibile": "Correzione disponibile",
                        "risolto": "Risolto", "duplicato": "Duplicato",
                        "non-riproducibile": "Non riproducibile"}
        visible = 0
        for i, issue in enumerate(entries):
            title = issue.get("title") or (issue.get("operation", "") + " — " +
                                             issue.get("category", "Problema"))
            if query and query not in (str(issue.get("number", "")) + " " + title).casefold():
                continue
            if issue_filter == "Aperti" and issue.get("state") == "closed":
                continue
            if issue_filter == "Chiusi" and issue.get("state") != "closed":
                continue
            if issue_filter == "Correzione disponibile" and not issue.get("fix_available"):
                continue
            fixed = issue.get("fixed_in")
            state = status_names.get(issue.get("triage")) or (
                "Chiuso" if issue.get("state") == "closed" else "Aperto")
            self.issue_table.insert("", "end", iid=str(i),
                values=("#" + str(issue["number"]), title, state,
                        issue.get("priority") or "Da valutare",
                        ("Disponibile: " if issue.get("fix_available") else "") +
                        (fixed or "Da definire")))
            visible += 1
        self.issue_status.set(str(visible) + " di " + str(len(entries)) +
                              " segnalazioni. Doppio clic per aprire GitHub.")

    def show_tracked_issue_details(self, _event=None):
        """Show locally cached issue metadata without exposing raw diagnostics."""
        chosen = self.issue_table.selection()
        entries = issue_tracker.history()
        if not chosen or not chosen[0].isdigit() or int(chosen[0]) >= len(entries):
            self.issue_details.set("Seleziona una segnalazione per visualizzarne i dettagli.")
            return
        issue = entries[int(chosen[0])]
        title = issue.get("title") or issue.get("category") or "Problema non classificato"
        fields = [("Problema", title), ("Issue", "#" + str(issue.get("number", "?"))),
                  ("Operazione", issue.get("operation")), ("Versione segnalata", issue.get("version")),
                  ("Prima segnalazione", issue.get("reported_at")),
                  ("Ultimo aggiornamento GitHub", issue.get("updated_at")),
                  ("Commenti GitHub", issue.get("comments")),
                  ("Origine", "Importata da GitHub" if issue.get("tracked_via") == "github"
                   else "Segnalata da questa installazione"),
                  ("Stato triage", issue.get("triage")),
                  ("Stato GitHub", issue.get("state")),
                  ("Priorità", issue.get("priority")),
                  ("Correzione prevista", issue.get("fixed_in")),
                  ("Aggiornamento disponibile", "Sì" if issue.get("fix_available") else "No")]
        timeline = issue.get("timeline") or []
        if timeline:
            fields.append(("Cronologia osservata", str(len(timeline)) + " variazioni"))
            for event in timeline[-5:]:
                changes = event.get("changes") or {}
                details = ", ".join(str(k) + ": " + str(v.get("from") or "—") + " → " +
                                    str(v.get("to") or "—") for k, v in changes.items())
                fields.append((str(event.get("observed_at") or "Data sconosciuta"), details))
        self.issue_details.set("\n".join(label + ": " + str(value if value not in (None, "") else "Non disponibile")
                                         for label, value in fields))

    def open_tracked_issue(self, _event=None):
        chosen = self.issue_table.selection()
        if chosen:
            entries = issue_tracker.history()
            index = int(chosen[0])
            if index < len(entries):
                webbrowser.open(entries[index]["url"])

    def refresh_issue_tracker(self, silent=False):
        if "Stato bug" in self.tasks:
            return

        def check():
            try:
                latest = updater.release_info(VERSION)["version"]
            except Exception:
                latest = None
            try:
                entries, listed = issue_tracker.synchronize(VERSION, latest_version=latest)
                return entries, listed, None
            except issue_tracker.RemoteIssueError as exc:
                # Expected external-service failure: keep the local history untouched.
                return issue_tracker.history(), {}, exc

        def finished(result):
            entries, _, remote_error = result
            self.render_issue_tracker()
            if remote_error is not None:
                label = ("Sincronizzazione non disponibile: " + str(remote_error)
                         + " I dati locali non sono stati modificati. Riprova quando la connessione è disponibile.")
                self.issue_status.set(label)
                if not silent:
                    messagebox.showwarning("Verifica stato Issue non disponibile", label, parent=self)
                return
            ready = [i for i in entries if i.get("fix_available")]
            if ready:
                label = ("Nuova versione disponibile con correzioni per "
                         + ", ".join("#" + str(i["number"]) for i in ready[:5]))
                self.issue_status.set(label)
                if silent:
                    self.toast.show(label, "success")
                else:
                    messagebox.showinfo("Correzione disponibile", label, parent=self)
            elif not silent:
                self.toast.show("Stato delle Issue aggiornato.", "success")

        self.run_task("Stato bug", check, finished)

    def report_update_failure(self):
        failure, self.update_failure = self.update_failure, None
        updater.clear_failure()
        if not failure:
            return
        # Opt-in as every report: the standard dialog shows the full report and
        # asks for confirmation before publishing. No network inventory: it is
        # not relevant to the updater and would only add personal data.
        self.show_error_dialog("Aggiornamento non riuscito", "Aggiornamento",
                               updater.failure_message(failure), "",
                               include_inventory=False)

    def check_updates(self, silent=False):
        if "Aggiornamenti" in self.tasks or "Download aggiornamento" in self.tasks:
            return
        def found(info):
            if info.get("error"):
                if not silent:
                    messagebox.showwarning(
                        "Controllo aggiornamenti non disponibile",
                        info["error"], parent=self)
                return
            if not info["available"]:
                if not silent:
                    messagebox.showinfo("WinNAT UI", "La versione " + VERSION
                                        + " è già aggiornata.", parent=self)
                return
            if not getattr(sys, "frozen", False):
                if not silent:
                    messagebox.showinfo("Nuova versione " + info["version"],
                                        "È disponibile una release ufficiale. "
                                        "L'aggiornamento in-app richiede il pacchetto EXE Windows.",
                                        parent=self)
                return
            if self.pending or "Commit" in self.tasks:
                self.toast.show("Nuova versione " + info["version"] +
                                " disponibile. Completa o annulla le modifiche prima di aggiornare.", "warning")
                return
            if not messagebox.askyesno(
                    "Aggiornamento disponibile",
                    "Versione installata: " + VERSION + "\n"
                    "Versione disponibile: " + info["version"] + "\n\n"
                    "Scaricare da GitHub e verificare l'integrità SHA256? "
                    "L'applicazione si chiuderà per completare l'aggiornamento.",
                    parent=self):
                return
            if self.pending or self.tasks:
                self.toast.show("Operazioni in corso: termina il lavoro prima di aggiornare.", "warning")
                return
            self.run_task("Download aggiornamento", lambda: updater.prepare(info),
                          lambda staging: self._install_update(staging, info["version"]))
        def lookup():
            try:
                return updater.release_info(VERSION)
            except ValueError as error:
                # Metadata and security validation failures are actionable update
                # errors, not an unclassified failure of the networking backend.
                return {"error": "Release GitHub non utilizzabile: " + str(error)}
            except Exception:
                if silent:
                    # Offline/blocked access at startup must not interrupt networking work.
                    return {"error": "Controllo automatico non disponibile."}
                raise
        self.run_task("Aggiornamenti", lookup, found)

    def _install_update(self, staging, version=""):
        if self.pending or self.tasks:
            messagebox.showwarning("Aggiornamento rinviato",
                                   "Completa le modifiche prima di riavviare.", parent=self)
            return
        if getattr(self, "_update_launching", False):
            return
        try:
            helper = updater.launch(staging, from_version=VERSION, to_version=version)
        except Exception as error:
            self.show_error_dialog("Aggiornamento non avviato", "Update", str(error),
                                   traceback.format_exc())
            return
        # Close only once the update window is on screen, so there is no gap
        # without any window; the deadline keeps the old behavior as a fallback.
        self._update_launching = True
        self.toast.show("Apertura della finestra di aggiornamento\u2026", "info", ms=UPDATE_WINDOW_WAIT_MS)
        try:
            self.configure(cursor="watch")
        except tk.TclError:
            pass
        self._close_when_update_window_ready(helper, staging,
                                             time.monotonic() + UPDATE_WINDOW_WAIT_MS / 1000)

    def _close_when_update_window_ready(self, helper, staging, deadline):
        exited = helper is not None and helper.poll() is not None
        if updater.helper_ready(staging) or exited or time.monotonic() >= deadline:
            self.destroy()
            return
        self.after(100, lambda: self._close_when_update_window_ready(helper, staging, deadline))

    # ------------------------------------------------------- navigation ---
    def show_page(self, key):
        if self.current == key:
            return
        for k, page in self.pages.items():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, (btn, marker, glyph, _count) in self.nav.items():
            active = k == key
            btn.configure(style="NavActive.TButton" if active else "Nav.TButton")
            marker.configure(bg=C["side_accent"] if active else C["side_bg"])
            glyph.configure(bg=C["side_active"] if active else C["side_bg"],
                            fg=C["side_accent"] if active else C["side_muted"])
        self.current = key
        if key == "sessions":
            self.refresh_sessions()

    def bind_shortcuts(self):
        self.bind("<F5>", lambda e: self.refresh())
        self.bind("<Control-Return>", lambda e: self.commit())
        self.bind("<Control-f>", lambda e: (self.show_page("sessions"), self.session_entry.focus_set()))
        for i, (key, *_rest) in enumerate(PAGES):
            self.bind("<Control-Key-%d>" % (i + 1), lambda e, k=key: self.show_page(k))

    # ------------------------------------------------------------ tasks ---
    def show_error_dialog(self, title, operation, message, traceback_text="", commit=False,
                          include_inventory=True):
        """Readable summary first; complete, copyable debug details on demand."""
        dlg = Dialog(self, title, "Chiudi", cancel="Copia errore")
        dlg.ok.configure(command=dlg.destroy)
        # The diagnostic report embeds the original error and traceback.
        # Build once: the same report shown here is sent to the gateway.
        payload = issue_tracker.safe_payload(
            operation, message, traceback_text, VERSION,
            inventory=self.data if include_inventory else None, is_admin=self.is_admin,
            pending=self.pending if include_inventory else None)
        report_title, report_body = bug_report.format_report(payload)
        report_text = report_title + "\n\n" + report_body

        def copy_report():
            dlg.clipboard_clear()
            dlg.clipboard_append(report_text)
            dlg.update()
            dlg.cancel_btn.configure(text="Copiato")

        def report_bug():
            if "Segnala bug" in self.tasks:
                return
            if not messagebox.askyesno(
                    "Pubblica diagnostica dettagliata",
                    "Questa segnalazione creerà o aggiornerà una Issue GitHub PUBBLICA.\n\n"
                    "Include messaggio di errore, traceback, comandi e output PowerShell, "
                    "dati di rete disponibili (IP, subnet e nomi interfacce) e ambiente.\n\n"
                    "Password e token riconoscibili vengono oscurati, ma il filtraggio "
                    "non garantisce di eliminare ogni informazione riservata.\n\n"
                    "Controlla e copia il report dai dettagli tecnici prima di procedere.\n\n"
                    "Confermi la pubblicazione?", parent=dlg):
                return
            progress = ProgressDialog(dlg, "Invio segnalazione",
                                      "Invio della diagnostica dettagliata a GitHub…")
            def send():
                # Remote availability check runs on a worker, not the Tk thread.
                endpoint = issue_tracker.service_endpoint()
                if endpoint is None:
                    raise RuntimeError("Servizio per la creazione anonima delle Issue non configurato.")
                # The gateway itself handles deduplication. Do not make a
                # separate GitHub Issues API lookup: it may be rate-limited
                # or unavailable, even while the gateway is operational.
                result = issue_tracker.submit(payload, endpoint=endpoint)
                issue_tracker.save_entry(payload, result)
                return result
            def close_error_dialog():
                if dlg.winfo_exists():
                    dlg.destroy()
            def sent(result):
                self.render_issue_tracker()
                number = "Issue #" + str(result["number"])
                if result["already_exists"]:
                    heading, description = "Diagnostica aggiunta a Issue esistente", number + " aggiornata."
                else:
                    heading, description = "Bug segnalato", number + " aperta correttamente."
                self.notice.set(heading + ": " + number)
                progress.succeed(heading, description + " Tracciamento locale attivato.",
                                 url=result["url"], on_close=close_error_dialog)
            def failed(error_message):
                # Reporting failures must not become new reportable errors.
                progress.fail("Segnalazione non inviata",
                              "Non è stato possibile creare la Issue su GitHub.\n" + error_message
                              + "\n\nIl report diagnostico originale rimane disponibile. Puoi riprovare.",
                              retry=report_bug)
            self.run_task("Segnala bug", send, sent, on_error=failed)
        dlg.cancel_btn.configure(command=copy_report)
        dlg.cancel_btn.configure(text="Copia report")
        report_actions = tk.Frame(dlg.body, bg=C["surface"])
        report_actions.pack(fill="x", pady=(0, S2))
        ttk.Button(report_actions, text="Segnala bug su GitHub",
                   command=report_bug).pack(side="left")
        tk.Label(report_actions, text="Report completo: IP e topologia inclusi. Verifica prima di pubblicare.",
                 font=F["caption"], bg=C["surface"], fg=C["text_muted"]).pack(
                     side="left", padx=S2)
        tk.Label(dlg.body, text=error_summary(message), font=F["body"], bg=C["surface"], fg=C["text"],
                 wraplength=560, justify="left", anchor="w").pack(fill="x", anchor="w")
        if commit:
            ui.Callout(dlg.body, kind="warning", wraplength=520,
                       text="Alcune modifiche potrebbero essere gi\u00e0 state applicate. Lo stato viene "
                            "riletto da Windows: controllalo prima di preparare un nuovo Commit.").pack(fill="x", pady=(S3, 0))
        panel = tk.Frame(dlg.body, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        viewer = tk.Text(panel, wrap="none", height=16, width=92, font=F["mono_s"], bd=0, padx=S2, pady=S2,
                         bg=C["surface_alt"], fg=C["text"], insertbackground=C["text"],
                         selectbackground=C["select"], selectforeground=C["text"], undo=False)
        sy = ttk.Scrollbar(panel, orient="vertical", command=viewer.yview)
        sx = ttk.Scrollbar(panel, orient="horizontal", command=viewer.xview)
        viewer.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        viewer.pack(side="left", fill="both", expand=True)
        viewer.insert("1.0", report_text)
        viewer.configure(state="disabled")
        viewer.bind("<Control-a>", lambda e: (viewer.tag_add("sel", "1.0", "end-1c"), "break")[1])
        toggle = ttk.Button(dlg.body, text="Mostra report da inviare", style="CardGhost.TButton")

        def toggle_debug():
            if panel.winfo_ismapped():
                panel.pack_forget()
                toggle.configure(text="Mostra report da inviare")
            else:
                panel.pack(fill="both", expand=True, pady=(S2, 0))
                toggle.configure(text="Nascondi report da inviare")
            dlg.recenter()
        toggle.configure(command=toggle_debug)
        toggle.pack(anchor="w", pady=(S3, 0))
        dlg.resizable(True, True)
        dlg.run(focus=dlg.ok)

    def run_task(self, key, fn, on_success, on_error=None):
        """Run ``fn`` on a worker; ``on_success(result)`` / ``on_error(message)`` run on the Tk thread."""
        if key in self.tasks:
            return
        self.tasks.add(key)
        self.notice.set(key + " in corso…")
        self.progress.start(11)

        def runner():
            try:
                self.work.put((key, True, fn(), (on_success, on_error)))
            except Exception as error:
                self.work.put((key, False, (str(error), traceback.format_exc()), (on_success, on_error)))
        threading.Thread(target=runner, daemon=True).start()
        self.render_changebar()

    def drain(self):
        # Re-arm first. A callback may open a modal dialog (wait_window runs a
        # nested event loop); if the next poll were scheduled only at the end,
        # results of tasks started from that dialog (e.g. "Segnala bug" from
        # the error dialog) would stay queued until the dialog was closed.
        self.after(100, self.drain)
        try:
            while True:
                key, ok, value, callbacks = self.work.get_nowait()
                if key == "__commit_log__":
                    self.append_commit_log(value[0], value[1])
                    continue
                callback, on_error = callbacks if isinstance(callbacks, tuple) else (callbacks, None)
                self.tasks.discard(key)
                if not self.tasks:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                if ok:
                    callback(value)
                else:
                    error_message, error_traceback = value
                    self.notice.set("Errore: " + error_summary(error_message)[:80])
                    if on_error is not None:
                        on_error(error_message)
                    elif key == "Commit":
                        # Keep the desired-state candidate. The refresh below reads
                        # Windows again; the next Apply recomputes a minimal diff and
                        # only retries what is still missing.
                        self.render_candidate()
                        self.show_error_dialog("Commit non riuscito", key,
                                               error_message, error_traceback, commit=True)
                        self.refresh()
                    elif key == "Segnala bug":
                        # Failure of the reporting facility must never become
                        # another reportable bug (infinite reporting loop).
                        messagebox.showwarning(
                            "Segnalazione non inviata",
                            "Non è stato possibile creare la Issue su GitHub.\n"
                            + error_message
                            + "\n\nL'errore originale resta consultabile: puoi copiarne "
                              "il report diagnostico e riprovare più tardi.",
                            parent=self)
                    else:
                        self.show_error_dialog("Operazione non riuscita", key, error_message, error_traceback)
                self.render_changebar()
        except queue.Empty:
            pass

    def refresh(self):
        self.run_task("Lettura configurazione", network.collect, self.render)

    # ----------------------------------------------------------- render ---
    def default_routes(self):
        routes = [r for r in (self.data or {}).get("routes", []) if r.get("DestinationPrefix") == "0.0.0.0/0"]
        routes.sort(key=lambda r: int(r.get("RouteMetric") or 0) + int(r.get("InterfaceMetric") or 0))
        return routes

    def render(self, data):
        self.data = data
        adapter_names = [a["Name"] for a in data.get("adapters", [])]
        self.lan_box["values"] = adapter_names
        routes = self.default_routes()
        online = [r.get("InterfaceAlias") for r in routes]
        if adapter_names and self.lan.get() not in adapter_names:
            offline = [n for n in adapter_names if n not in online]
            self.lan.set("Ethernet" if "Ethernet" in adapter_names else (offline or adapter_names)[0])
        # Drop WAN rows whose adapter disappeared; keep at least one row.
        self.wan_rows[:] = [r for r in self.wan_rows if r["alias"].get() in adapter_names] or self.wan_rows[:1]
        first = self.wan_rows[0]["alias"]
        if first.get() not in adapter_names or first.get() == self.lan.get():
            choice = [n for n in online if n != self.lan.get()]
            first.set(choice[0] if choice else "")
        self.layout_wan_rows()
        self.on_lan_changed()
        # Refresh the detected DHCP/static state without overwriting the
        # user's candidate address or prefix after a successful commit.
        self.subnet_source = network_guide.detect_lan_subnet(self.data, self.lan.get())
        self.show_subnet_source()

        lines = ["WAN prevista: " + (routes[0].get("InterfaceAlias", "?") if routes else "nessuna default route"), "",
                 "Interfacce e indirizzi IPv4:"]
        for a in data.get("adapters", []):
            ips = [f"{p['IPAddress']}/{p['PrefixLength']}" for p in data.get("ips", []) if p.get("InterfaceIndex") == a.get("InterfaceIndex")]
            lines.append(f"  {a['Name']} [{a.get('Status')}]  {', '.join(ips) or '-'}")
        lines.extend(["", "NAT rilevate: " + str(len(data.get("nats", []))),
                      "ICS: " + str(data.get("ics", {}).get("Status", "sconosciuto")),
                      "Condivisioni ICS: " + str([c.get("Name") for c in data.get("icsConnections", []) if c.get("SharingEnabled")])])
        lines.extend(["", "Routing IPv4 globale (IPEnableRouter): " + str(data.get("globalRouter", "?")),
                      "", "Impostazioni IPv4 delle interfacce:"])
        for iface in data.get("interfaces", []):
            if iface.get("InterfaceAlias") in adapter_names:
                lines.append("  %s: DHCP=%s | Forwarding=%s | Metrica=%s | Auto=%s" % (
                    iface.get("InterfaceAlias"), iface.get("Dhcp"), iface.get("Forwarding"),
                    iface.get("InterfaceMetric"), iface.get("AutomaticMetric")))
        lines.extend(["", "Default route WAN:"])
        for route in routes:
            lines.append("  %s via %s | metrica route %s + interfaccia %s" % (
                route.get("InterfaceAlias"), route.get("NextHop"), route.get("RouteMetric"), route.get("InterfaceMetric")))
        self.dashboard_base = "\n".join(lines)
        self.render_overview()
        self.render_candidate()
        self.validate_form()
        self.notice.set("Aggiornato alle " + time.strftime("%H:%M"))

    def render_overview(self):
        data = self.data or {}
        routes = self.default_routes()
        nats = data.get("nats", [])
        router = data.get("globalRouter")
        ics = data.get("ics", {}) or {}
        sharing = [c.get("Name") for c in data.get("icsConnections", []) if c.get("SharingEnabled")]
        ifaces = {i.get("InterfaceAlias"): i for i in data.get("interfaces", [])}
        forwarding = [k for k, v in ifaces.items() if is_on(v.get("Forwarding"))]

        badge, value, detail = self.kpis["wan"]
        if routes:
            badge.set("ONLINE", "success")
            value.configure(text=routes[0].get("InterfaceAlias", "?"))
            detail.configure(text="via " + str(routes[0].get("NextHop")) +
                             ("  ·  +" + str(len(routes) - 1) + " alternative" if len(routes) > 1 else ""))
        else:
            badge.set("OFFLINE", "danger")
            value.configure(text="Nessuna")
            detail.configure(text="Nessuna default route IPv4")
        badge, value, detail = self.kpis["nat"]
        value.configure(text=str(len(nats)) + (" regola" if len(nats) == 1 else " regole"))
        detail.configure(text=", ".join(str(n.get("Name")) + " → " + str(n.get("InternalIPInterfaceAddressPrefix"))
                                        for n in nats) or "Nessun NAT configurato")
        badge.set(*(("ATTIVO", "success") if any(is_on(n.get("Active")) for n in nats) else
                    ("PIÙ PREFISSI", "warning") if len(nats) > 1 else
                    ("INATTIVO", "warning") if nats else ("ASSENTE", "neutral")))
        if len(nats) > 1:
            badge.set("PIÙ PREFISSI", "warning")
        badge, value, detail = self.kpis["router"]
        value.configure(text="Abilitato" if is_on(router) else "Disabilitato")
        badge.set(*(("ON", "success") if is_on(router) else ("OFF", "neutral")))
        detail.configure(text="Forwarding su: " + (", ".join(forwarding) or "nessuna interfaccia"))
        badge, value, detail = self.kpis["ics"]
        value.configure(text=service_status(ics.get("Status")))
        detail.configure(text="Condivisione su: " + ", ".join(sharing) if sharing else "Nessuna condivisione attiva")
        badge.set(*(("CONFLITTO", "danger") if sharing and nats else ("IN USO", "warning") if sharing else ("OK", "success")))

        # Overall verdict: one sentence answering "is my gateway working?"
        if nats and is_on(router) and forwarding and routes:
            title, text, edge, cta = "Gateway NAT operativo", "NAT, routing e default route sono presenti.", C["success"], None
        elif nats or is_on(router):
            title, text, edge, cta = "Configurazione parziale", "Alcuni elementi del gateway mancano: controlla i riquadri sotto.", C["warning"], "Apri Gateway"
        else:
            title, text, edge, cta = "Gateway non configurato", "Il PC non sta instradando traffico per altri dispositivi.", C["border_strong"], "Configura gateway"
        self.hero_title.configure(text=title)
        self.hero_text.configure(text=text)
        self.hero_edge.configure(bg=edge)
        if cta:
            self.hero_cta.configure(text=cta)
            self.hero_cta.pack(side="right")
        else:
            self.hero_cta.pack_forget()

        lan, wans = self.lan.get(), [r["alias"].get() for r in self.wan_rows]
        default_alias = routes[0].get("InterfaceAlias") if routes else None
        t = self.iface_table
        t.delete(*t.get_children())
        for i, a in enumerate(data.get("adapters", [])):
            name = a.get("Name")
            ips = ", ".join(f"{p['IPAddress']}/{p['PrefixLength']}" for p in data.get("ips", [])
                            if p.get("InterfaceIndex") == a.get("InterfaceIndex")) or "—"
            info = ifaces.get(name, {})
            role = "LAN" if name == lan else ("WAN %d" % (wans.index(name) + 1) if name in wans else "")
            up = str(a.get("Status")) == "Up"
            status = ("●  " if up else "○  ") + ADAPTER_STATUS.get(str(a.get("Status")), str(a.get("Status") or "?"))
            if name == default_alias:
                status += "  ★"
            tags = ("odd",) if i % 2 else ()
            if not up:
                tags += ("muted",)
            t.insert("", "end", values=(name, role, status, ips, yes_no(info.get("Dhcp")),
                                        yes_no(info.get("Forwarding")), info.get("InterfaceMetric", "—")), tags=tags)
        t.configure(height=max(3, min(8, len(data.get("adapters", [])))))
        t = self.route_table
        t.delete(*t.get_children())
        for i, r in enumerate(routes):
            total = int(r.get("RouteMetric") or 0) + int(r.get("InterfaceMetric") or 0)
            t.insert("", "end", values=(("★ " if i == 0 else "   ") + str(r.get("InterfaceAlias")), r.get("NextHop"),
                                        r.get("RouteMetric"), r.get("InterfaceMetric"), total),
                     tags=("odd",) if i % 2 else ())
        t.configure(height=max(2, min(5, len(routes))))

    def render_candidate(self):
        self.nat_table.delete(*self.nat_table.get_children())
        nats = {n["Name"]: n for n in (self.data or {}).get("nats", [])}
        # Keep the displayed candidate aligned with the latest live inventory.
        # For convergent gateway apply this is a fresh diff, not the original script.
        for p in self.pending:
            if p["kind"] == "guide" and self.data:
                try:
                    action, profile, _fingerprint = p["args"]
                    p["details"] = "\n".join(network_guide.preview(action, profile, self.data))
                except Exception as exc:
                    p["details"] = "Verifica candidato: " + str(exc)
        removals = {p["args"][0] for p in self.pending if p["kind"] == "remove"}
        for name, n in nats.items():
            self.nat_table.insert("", "end", values=("- Da eliminare" if name in removals else "Applicata", name,
                                                     n.get("InternalIPInterfaceAddressPrefix", ""), yes_no(n.get("Active"))))
        for p in self.pending:
            if p["kind"] == "guide":
                act, profile, _fingerprint = p["args"]
                if act == "apply":
                    existing = nats.get(profile["nat"])
                    exact = (existing
                             and existing.get("InternalIPInterfaceAddressPrefix") == profile["prefix"]
                             and not existing.get("ExternalIPInterfaceAddressPrefix"))
                    if not exact:
                        self.nat_table.insert("", "end", values=("+ Da creare", profile["nat"], profile["prefix"], "Non ancora"))
                else:
                    for item in self.nat_table.get_children():
                        v = list(self.nat_table.item(item, "values"))
                        v[0] = "- Da eliminare"
                        self.nat_table.item(item, values=v)
            if p["kind"] == "add":
                self.nat_table.insert("", "end", values=("+ Da creare", p["args"][0], p["args"][1], "Non ancora"))
            if p["kind"] == "setup":
                self.nat_table.insert("", "end", values=("+ Setup", "WinNAT-UI", p["args"][1], "Non ancora"))
            if p["kind"] == "reset":
                for item in self.nat_table.get_children():
                    v = list(self.nat_table.item(item, "values"))
                    if v[1] in p["args"][0].get("nat_names", []):
                        v[0] = "- Da eliminare"
                        self.nat_table.item(item, values=v)
            if p["kind"] == "profile":
                self.nat_table.insert("", "end", values=("+ Setup", "WinNAT-UI", p["args"][0]["prefix"], "Non ancora"))
            if p["kind"] == "external_teardown":
                for item in self.nat_table.get_children():
                    v = list(self.nat_table.item(item, "values"))
                    if v[1] in p["args"][3]:
                        v[0] = "- Da eliminare"
                        self.nat_table.item(item, values=v)
            if p["kind"] == "teardown":
                state = network.managed_state()
                if state and state["nat"] in nats and state["nat"] not in removals:
                    for item in self.nat_table.get_children():
                        if self.nat_table.item(item, "values")[1] == state["nat"]:
                            v = list(self.nat_table.item(item, "values"))
                            v[0] = "- Da eliminare"
                            self.nat_table.item(item, values=v)
        for i, item in enumerate(self.nat_table.get_children()):
            v = list(self.nat_table.item(item, "values"))
            state = str(v[0])
            tag = "add" if state.startswith("+") else "remove" if state.startswith("-") else ("odd" if i % 2 else "")
            v[0] = {"+": "＋ ", "-": "− "}.get(state[:1], "✓ ") + state.lstrip("+- ")
            v[0] = ("+ " if state.startswith("+") else "- " if state.startswith("-") else "") + v[0][2:]
            self.nat_table.item(item, values=v, tags=(tag,) if tag else ())
        if self.nat_table.get_children():
            self.nat_empty.place_forget()
        else:
            self.nat_empty.place(relx=0.5, rely=0.5, anchor="center")
        self.nat_selected()

        self.render_secondary_ips()
        self.pending_table.delete(*self.pending_table.get_children())
        for p in self.pending:
            self.pending_table.insert("", "end", values=(p["label"], p["details"]))
        self.render_changes()
        self.wizard_notice.set("Modifiche da applicare: " + str(len(self.pending)))
        if hasattr(self, "dashboard_base"):
            shown = self.dashboard_base
            if self.pending:
                shown += "\n\n=== CONFIGURAZIONE CANDIDATA (NON APPLICATA) ===\n"
                shown += "\n".join(p["label"] + ": " + p["details"] for p in self.pending)
            self.dashboard.configure(state="normal")
            self.dashboard.delete("1.0", "end")
            self.dashboard.insert("end", shown)
            self.dashboard.configure(state="disabled")
        if self.pending:
            self.dash_pending.set(str(len(self.pending)) + " modifica in attesa, non ancora applicata: " +
                                  ", ".join(p["label"] for p in self.pending) + ".  Rivedi →", "warning")
            self.dash_pending.pack(fill="x", pady=(S3, 0), before=self.dash_iface_head)
        else:
            self.dash_pending.pack_forget()
        btn, marker, glyph, count = self.nav["changes"]
        if self.pending:
            count.configure(text=str(len(self.pending)))
            count.place(in_=btn, relx=1.0, x=-S3, rely=0.5, anchor="e")
        else:
            count.place_forget()
        self.render_changebar()

    def render_changebar(self):
        if not hasattr(self, "cb_title"):
            return
        n = len(self.pending)
        busy = "Commit" in self.tasks
        if n == 0:
            bg, kind, title = C["surface"], "success", "Nessuna modifica in attesa"
            hint = "La rete Windows non verrà toccata finché non prepari e applichi un'operazione."
        else:
            bg, kind = C["warning_soft"], "warning"
            title = (str(n) + " modifica in attesa" if n == 1 else str(n) + " modifiche in attesa") + " · non ancora applicata"
            if not self.is_admin:
                hint = "Per applicarla avvia WinNAT UI come amministratore."
            elif n > 1:
                hint = "Applica una modifica per volta: rimuovi le altre dalla sezione Modifiche."
            else:
                hint = "In caso di errore verrà tentato un rollback dalle configurazioni precedenti, senza garanzia di ripristino completo."
        if busy:
            title, hint = "Applicazione in corso…", "Non chiudere l'app finché l'operazione non termina."
        for w in self.cb_widgets:
            w.configure(bg=bg)
        self.changebar_line.configure(bg=C["warning"] if n else C["border"])
        self.cb_icon.configure(text=ui.icon("warning" if n else "ok"), fg=C[kind])
        self.cb_title.configure(text=title)
        self.cb_hint.configure(text=hint)
        can_commit = n == 1 and self.is_admin and not self.tasks
        self.commit_button.configure(state="normal" if can_commit else "disabled")
        for b in (self.discard_button, self.review_button, self.commit_button):
            b.pack_forget()
        if n:  # progressive disclosure: actions appear only when there is something to act on
            self.commit_button.pack(side="right", before=self.cb_texts)
            self.review_button.pack(side="right", padx=S2, before=self.cb_texts)
            self.discard_button.pack(side="right", before=self.cb_texts)
        for b in (self.review_button, self.discard_button):
            b.configure(state="disabled" if busy else "normal")

    # ---------------------------------------------------------- staging ---
    def stage(self, kind, args, label, details):
        if any(p["kind"] == kind and p["args"] == args for p in self.pending):
            return
        checkpoint = network.save_commit_state(
            "candidate-commit", self.data or {},
            {"kind": kind, "label": label, "details": details})
        self.pending.append(dict(kind=kind, args=args, label=label, details=details,
                                 candidate_snapshot=checkpoint))
        self.render_candidate()
        self.toast.show("«" + label + "» aggiunta alle modifiche in attesa.", "info")

    def add(self):
        if self.data is None:
            return self.toast.show("Attendi il caricamento della configurazione.", "warning")
        dlg = Dialog(self, "Aggiungi regola NAT", "Aggiungi alle modifiche")
        name, prefix = tk.StringVar(value="WinNAT-UI"), tk.StringVar(value="192.168.1.0/24")
        entries = {}
        for key, label, var in (("name", "Nome della regola", name), ("prefix", "Rete interna (CIDR)", prefix)):
            ttk.Label(dlg.body, text=label, style="Card.TLabel").pack(anchor="w")
            e = ttk.Entry(dlg.body, textvariable=var, width=42)
            e.pack(anchor="w", fill="x", pady=(S1, 0))
            msg = ttk.Label(dlg.body, text="", style="Card.Error.TLabel")
            msg.pack(anchor="w", pady=(2, S3))
            entries[key] = (e, msg)

        def check(*_):
            errs = {}
            try:
                network.validate_name(name.get().strip())
            except ValueError as exc:
                errs["name"] = str(exc)
            try:
                network.validate_prefix(prefix.get().strip())
            except ValueError as exc:
                errs["prefix"] = friendly_ip_error(exc, "192.168.1.0/24")
            for key, (e, msg) in entries.items():
                msg.configure(text=errs.get(key, ""))
                e.configure(style="Invalid.TEntry" if key in errs else "TEntry")
            dlg.ok.configure(state="disabled" if errs else "normal")
        name.trace_add("write", check)
        prefix.trace_add("write", check)
        check()
        dlg.bind("<Return>", lambda e: dlg.accept())
        if dlg.run(focus=entries["name"][0]):
            n, pfx = name.get().strip(), network.validate_prefix(prefix.get().strip())
            details = n + " / " + pfx
            self.stage("add", (n, pfx), "Aggiungi NAT", details)

    def remove(self):
        selected = self.nat_table.selection()
        if not selected:
            return self.toast.show("Seleziona prima una regola NAT.", "info")
        values = self.nat_table.item(selected[0], "values")
        if str(values[0]).startswith("+"):
            self.pending = [p for p in self.pending if not (p["kind"] == "add" and p["args"][0] == values[1])]
            self.render_candidate()
            return
        if str(values[0]).startswith("-"):
            return
        self.stage("remove", (values[1],), "Elimina NAT", str(values[1]))

    def setup(self):
        if self.data is None:
            return
        try:
            lan = self.lan.get()
            prefix = network.validate_prefix(self.prefix.get())
            gateway = network.validate_gateway(self.gateway.get(), ipaddress.IPv4Network(prefix))
            network.validate_alias(lan, self.data)
        except Exception as exc:
            return messagebox.showerror("Dati non validi", str(exc))
        plan = {"lan": lan, "wan": self.wan_rows[0]["alias"].get(), "prefix": prefix, "gateway": gateway}
        try:
            network_plan.preflight(plan, self.data)
        except Exception as exc:
            return messagebox.showwarning("Prerequisiti setup", str(exc))
        self.stage("profile", (plan,), "Configura LAN/WAN", lan + " -> " + plan["wan"] + " | " + prefix + " | gateway " + gateway)
        self.show_page("changes")

    def teardown(self):
        state = network.managed_state()
        if not state:
            return messagebox.showinfo("Configurazione", "Non esiste un setup registrato dall'app.")
        self.stage("teardown", (), "Rimuovi configurazione", state["lan"] + " | " + state["prefix"])

    def prepare_guide(self, action):
        target = self.setup_issue if action == "apply" else self.teardown_issue
        target.pack_forget()
        if not self.data:
            return self.toast.show("Attendi il caricamento della configurazione.", "warning")
        if "Commit" in self.tasks:
            return self.toast.show("Attendi che l'applicazione in corso sia terminata.", "warning")
        try:
            profile = self.form_profile()
            lines = network_guide.preview(action, profile, self.data)
            normalized = network_guide.validate(profile, self.data, action)
            signature = network_guide.fingerprint(normalized, self.data)
        except Exception as exc:
            target.set(str(exc), "danger")
            target.pack(fill="x", pady=(0, S3))
            if action != "apply":
                target.pack(after=self.scope_label)
            return
        if self.pending:
            dlg = Dialog(self, "Sostituire le modifiche in attesa?", "Sostituisci")
            tk.Label(dlg.body, text="Hai già " + str(len(self.pending)) + " modifica/e preparata/e. "
                     "Verranno sostituite da questa operazione.", font=F["body"], bg=C["surface"], fg=C["text"],
                     wraplength=380, justify="left").pack(anchor="w")
            if not dlg.run():
                return
        self.pending.clear()
        labels = {"apply": "Configura gateway", "disable": "Disabilita gateway", "reset": "Ripristina rete"}
        self.stage("guide", (action, normalized, signature), labels[action], "\n".join(lines))
        self.show_page("changes")

    def unstage(self, position=None):
        if position is None:
            selected = self.pending_table.selection()
            if not selected:
                return
            position = self.pending_table.index(selected[0])
        del self.pending[position]
        self.render_candidate()

    def discard(self):
        if not self.pending:
            return
        dlg = Dialog(self, "Scartare le modifiche?", "Scarta modifiche", kind="Danger", cancel="Mantieni")
        tk.Label(dlg.body, text="Le " + str(len(self.pending)) + " operazioni in attesa verranno eliminate.\n"
                 "La configurazione di Windows non cambia.", font=F["body"], bg=C["surface"], fg=C["text"],
                 justify="left").pack(anchor="w")
        if dlg.run():
            self.pending.clear()
            self.render_candidate()
            self.toast.show("Modifiche scartate.", "info")

    def confirm_commit(self, changes):
        dlg = Dialog(self, "Applicare la modifica alla rete?", "Applica ora", kind="Danger")
        for i, p in enumerate(changes):
            tk.Label(dlg.body, text=str(i + 1) + ".  " + p["label"], font=F["strong"], bg=C["surface"],
                     fg=C["text"]).pack(anchor="w")
            box = tk.Frame(dlg.body, bg=C["surface_alt"])
            box.pack(fill="x", pady=(S1, S3))
            for line in [l for l in str(p["details"]).split("\n") if not l.startswith("ATTENZIONE")]:
                tk.Label(box, text="•  " + line, font=F["caption"], bg=C["surface_alt"], fg=C["text_muted"],
                         anchor="w", justify="left", wraplength=500).pack(anchor="w", padx=S3, pady=1)
        ui.Callout(dlg.body, kind="warning", wraplength=470,
                   text="La connessione può interrompersi. In caso di errore sarà tentato un rollback "
                        "delle risorse coinvolte; Windows non garantisce il ripristino completo.").pack(fill="x", pady=(0, S3))
        ack = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg.body, text="Sto usando il PC in locale e accetto l'interruzione della rete",
                        variable=ack, style="Card.TCheckbutton").pack(anchor="w")
        dlg.ok.configure(state="disabled")
        ack.trace_add("write", lambda *a: dlg.ok.configure(state="normal" if ack.get() else "disabled"))
        return dlg.run()

    def commit(self):
        if not self.pending:
            return
        if not network.admin():
            return self.toast.show("Avvia WinNAT UI come amministratore per applicare modifiche.", "warning")
        if self.tasks:
            return self.toast.show("Attendi che le operazioni correnti siano terminate.", "warning")
        changes = list(self.pending)
        if len(changes) != 1:
            self.show_page("changes")
            return self.toast.show("Applica una modifica per volta: rimuovi le altre dall'elenco.", "warning")
        if not self.confirm_commit(changes):
            return

        def execute():
            # The pending item is a desired state. Read Windows immediately before
            # writing, persist the checkpoint and let each operation converge from
            # that fresh inventory.
            current = network.collect()
            commit_context = {
                "changes": [
                    {"kind": p["kind"], "label": p["label"], "details": p["details"],
                     "candidate_snapshot": p.get("candidate_snapshot")}
                    for p in changes
                ]
            }
            pre_state_path = network.save_commit_state("pre-commit", current, commit_context)
            backup_path = network.snapshot(current)
            completed = []
            for p in changes:
                kind, args = p["kind"], p["args"]
                scope = network_rollback.scope_for(kind, args, current)
                try:
                    nats = current.get("nats", [])
                    post_inventory = None
                    if kind == "add":
                        disposition = network.nat_add_preflight(args[0], args[1], current)
                        if disposition == "create":
                            # Aggiungi NAT means exactly New-NetNat. Never migrate,
                            # widen, delete or rebuild a pre-existing NAT object.
                            network.create_nat(*args)
                            verified = network.collect()
                            created = [n for n in verified.get("nats", [])
                                       if n.get("Name") == args[0] and
                                       n.get("InternalIPInterfaceAddressPrefix") == args[1]]
                            if len(created) != 1:
                                raise RuntimeError("New-NetNat eseguito, ma verifica del NAT creato non riuscita.")
                            post_inventory = verified
                        else:
                            # Idempotent retry for an identical rule.
                            post_inventory = current
                    elif kind == "remove":
                        if any(n.get("Name") == args[0] for n in nats):
                            network.remove_nat(*args)
                    elif kind == "setup":
                        network.setup(*args, current)
                    elif kind == "guide":
                        result = network_guide.execute(args[0], args[1], current, args[2], verify=True)
                        post_inventory = result.get("post_inventory")
                    elif kind == "profile":
                        network_plan.apply_profile(args[0], current)
                    elif kind == "lan_ip":
                        action, alias, address, prefix, old_ip, old_prefix, index = args
                        candidate = secondary_ips.plan(
                            action, alias, address, prefix, current,
                            old_address=old_ip, old_prefix=old_prefix, expected_index=index)
                        secondary_ips.apply(candidate)
                        verified = network.collect()
                        secondary_ips.verify(candidate, verified)
                        post_inventory = verified
                    elif kind == "reset":
                        # Recompute the exact resources at commit time; abort if the inventory changed.
                        expected = network_plan.matching_resources(self.data, args[0])
                        actual = network_plan.matching_resources(current, args[0])
                        if expected != actual:
                            raise ValueError("La configurazione è cambiata dopo l'anteprima: aggiorna e prepara di nuovo il ripristino.")
                        network_plan.remove_selected(args[0], current)
                    elif kind == "teardown":
                        network.teardown(current)
                    elif kind == "external_teardown":
                        network.remove_existing_configuration(args[0], args[1], args[2], args[3], current, args[4])
                    completed.append(p)
                    current = post_inventory if post_inventory is not None else network.collect()
                except Exception as original:
                    # A failed read-only preflight cannot have modified Windows.
                    # Avoid a pointless rollback and preserve the actionable error.
                    if kind in ("add", "lan_ip") and isinstance(original, ValueError):
                        raise RuntimeError("COMMIT BLOCCATO PRIMA DELLE MODIFICHE: "
                                           + str(original)
                                           + "\nStato pre-commit: " + str(pre_state_path)) from original
                    try:
                        report = network_rollback.rollback(current, scope, backup_path)
                        try:
                            rollback_state = network.collect()
                            rollback_path = network.save_commit_state(
                                "post-rollback", rollback_state,
                                {"pre_commit": pre_state_path, "error": str(original)})
                            report += "\nStato post-rollback: " + rollback_path
                        except Exception:
                            pass
                    except Exception as rollback_error:
                        raise RuntimeError(
                            "COMMIT FALLITO: " + str(original) + "\n\n"
                            "ROLLBACK INCOMPLETO O NON VERIFICABILE:\n" + str(rollback_error)
                            + "\nSnapshot: " + str(backup_path)
                            + "\nStato pre-commit: " + str(pre_state_path)) from original
                    raise RuntimeError(
                        "COMMIT FALLITO: " + str(original) + "\n\n" + report
                        + "\nSnapshot: " + str(backup_path)
                        + "\nStato pre-commit: " + str(pre_state_path)) from original
            post_state_path = network.save_commit_state(
                "post-commit", current,
                {"pre_commit": pre_state_path, "changes": commit_context["changes"]})
            return {"completed": completed, "pre_state": pre_state_path,
                    "post_state": post_state_path}

        def success(result):
            applied = result["completed"] if isinstance(result, dict) else result
            self.pending = [p for p in self.pending if p not in applied]
            self.render_candidate()
            router_changed = any(p["kind"] == "guide" for p in applied)
            self.toast.show("Modifica applicata." + (" Riavvia Windows prima dei test end-to-end: "
                                                    "IPEnableRouter è cambiato." if router_changed else ""),
                            "success", ms=9000 if router_changed else 4000)
            self.refresh()
        self.show_page("changes")
        self.clear_commit_log()
        self.append_commit_log("info", "Avvio commit · " + changes[0]["label"])
        def execute_logged():
            token = network.command_logger.set(
                lambda kind, message: self.work.put(
                    ("__commit_log__", True, (kind, message), None)))
            try:
                self.work.put(("__commit_log__", True,
                               ("info", "Snapshot della configurazione e verifiche preliminari"), None))
                result = execute()
                if isinstance(result, dict):
                    self.work.put(("__commit_log__", True,
                                   ("info", "Stato pre-commit: " + result.get("pre_state", "n/d")), None))
                    self.work.put(("__commit_log__", True,
                                   ("info", "Stato post-commit: " + result.get("post_state", "n/d")), None))
                self.work.put(("__commit_log__", True, ("info", "Commit completato"), None))
                return result
            except Exception as exc:
                self.work.put(("__commit_log__", True, ("stderr", "Errore commit: " + str(exc)), None))
                raise
            finally:
                network.command_logger.reset(token)
        self.run_task("Commit", execute_logged, success)

    # --------------------------------------------------------- sessions ---
    def periodic_sessions(self):
        if self.current == "sessions":
            self.refresh_sessions()
        self.after(60000, self.periodic_sessions)

    def refresh_sessions(self):
        self.run_task("Lettura sessioni", network.sessions, self.store_sessions)

    def store_sessions(self, rows):
        self.session_rows = rows
        self.session_updated = time.strftime("%H:%M:%S")
        self.show_sessions(rows)
        self.notice.set("Sessioni aggiornate alle " + self.session_updated)

    def show_sessions(self, rows):
        self.session_table.delete(*self.session_table.get_children())

        def endpoint(obj, ip, port):
            return str(obj.get(ip) or "") + (":" + str(obj[port]) if obj.get(port) is not None else "")
        needle = self.session_filter.get().strip().lower()
        shown = 0
        for s in rows:
            values = (s.get("NatName") or "", PROTOCOLS.get(s.get("Protocol"), str(s.get("Protocol") or "")),
                      endpoint(s, "InternalSourceAddress", "InternalSourcePort"),
                      endpoint(s, "InternalDestinationAddress", "InternalDestinationPort"),
                      endpoint(s, "ExternalSourceAddress", "ExternalSourcePort"))
            if needle and needle not in " ".join(map(str, values)).lower():
                continue
            self.session_table.insert("", "end", values=values, tags=("odd",) if shown % 2 else ())
            shown += 1
        total = len(rows)
        updated = getattr(self, "session_updated", None)
        text = (str(shown) + " di " + str(total) if needle else str(total)) + (" sessione" if total == 1 else " sessioni")
        self.session_status.set(text + ("  ·  aggiornate alle " + updated if updated else ""))

    def export(self):
        if self.data is None:
            return
        file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialfile="winnat-diagnostica-" + time.strftime("%Y%m%d-%H%M") + ".json")
        if file:
            with open(file, "w", encoding="utf-8") as output:
                json.dump(self.data, output, indent=2, ensure_ascii=False)
            self.toast.show("Diagnostica esportata.", "success")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows richiesto")
    App().mainloop()
