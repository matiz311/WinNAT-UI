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
from tkinter import ttk, messagebox, filedialog
import network
import network_plan
import network_guide
import network_rollback
import ui_theme as ui
from version import VERSION
from ui_theme import C, F, S1, S2, S3, S4, S5

REPO_URL = "https://github.com/matiz311/WinNAT-UI"

PAGES = [  # key, label, icon, subtitle
    ("dashboard", "Panoramica", "dashboard", "Stato reale della rete Windows, in sola lettura."),
    ("nat", "Regole NAT", "nat", "Regole WinNAT applicate e modifiche in attesa di Commit."),
    ("network", "Gateway", "network", "Trasforma il PC in un gateway LAN → NAT → WAN."),
    ("changes", "Modifiche", "changes", "Controlla le operazioni preparate prima di applicarle."),
    ("sessions", "Sessioni", "sessions", "Traduzioni NAT attive in questo momento."),
    ("about", "Informazioni", "info", "Versione, scorciatoie e note di sicurezza."),
]
FIELD_TITLES = {"lan": "LAN", "wan1": "WAN primaria", "wan2": "WAN di riserva", "prefix": "Subnet LAN",
                "gateway": "IP del PC", "nat": "Nome NAT", "metric1": "Metrica primaria", "metric2": "Metrica di riserva"}
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


class Topology(tk.Canvas):
    """Live sketch of LAN \u2192 PC gateway \u2192 WAN(s) \u2192 Internet built from the form values.

    It turns abstract fields into a picture the user can check at a glance
    (recognition rather than recall): wrong interface = wrong arrow.
    """
    H = 196

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["surface"], highlightthickness=0, height=self.H)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())

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
        lan, wan1, wan2 = a.lan.get() or "LAN ?", a.wan1.get() or "WAN ?", a.wan2.get()
        prefix, gateway = a.prefix.get() or "?", a.gateway.get() or "?"
        col = [w * 0.11, w * 0.40, w * 0.69, w * 0.90]
        nw = min(170, w * 0.17)
        mid, top = 96, 18
        for x, text in ((col[0], "RETE LAN"), (col[1], "QUESTO PC"), ((col[2] + col[3]) / 2, "USCITA INTERNET")):
            self.create_text(x, top, text=text, fill=C["text_faint"], font=F["overline"])
        # LAN side
        self.create_line(col[0] + nw / 2, mid, col[1] - nw / 2 - 6, mid, fill=C["accent"], width=3, arrow="last",
                         arrowshape=(10, 12, 5))
        bad = getattr(self, "errors", {})
        self.node(col[0], mid, nw, 56, "Client / firewall", prefix,
                  C["danger"] if "prefix" in bad else C["border_strong"])
        self.node(col[1], mid, nw + 20, 64, "Gateway NAT", gateway,
                  C["danger"] if "gateway" in bad else C["accent"],
                  fill=C["danger_soft"] if "gateway" in bad else C["accent_soft"])
        self.chip((col[0] + col[1]) / 2, mid - 18, lan, C["accent"])
        # WAN side
        y1, y2 = (mid - 38, mid + 38) if wan2 else (mid, mid)
        x_out = col[1] + (nw + 20) / 2
        self.create_line(x_out, mid, col[2] - nw / 2, y1, fill=C["info"], width=3)
        self.node(col[2], y1, nw, 46, wan1, "primaria \u00b7 metrica " + (a.metric1.get() or "?"), C["info"])
        if wan2:
            self.create_line(x_out, mid, col[2] - nw / 2, y2, fill=C["text_faint"], width=2, dash=(6, 4))
            self.node(col[2], y2, nw, 46, wan2, "riserva \u00b7 metrica " + (a.metric2.get() or "?"), C["text_faint"], dashed=True)
        cx, r = col[3], min(44, w * 0.05)
        for dx, dy, k in ((-0.5, 0.15, 0.7), (0.05, -0.25, 0.85), (0.55, 0.12, 0.65), (0, 0.35, 0.7)):
            self.create_oval(cx + dx * r - k * r, mid + dy * r - k * r, cx + dx * r + k * r, mid + dy * r + k * r,
                             fill=C["surface_alt"], outline=C["border_strong"])
        for dx, dy, k in ((-0.5, 0.15, 0.7), (0.05, -0.25, 0.85), (0.55, 0.12, 0.65), (0, 0.35, 0.7)):
            self.create_oval(cx + dx * r - k * r + 2, mid + dy * r - k * r + 2, cx + dx * r + k * r - 2,
                             mid + dy * r + k * r - 2, fill=C["surface_alt"], outline="")
        self.create_text(cx, mid + 4, text="Internet", fill=C["text"], font=F["caption"])
        self.create_line(col[2] + nw / 2, y1, cx - r, mid, fill=C["info"], width=3, arrow="last", arrowshape=(10, 12, 5))
        if wan2:
            self.create_line(col[2] + nw / 2, y2, cx - r, mid, fill=C["text_faint"], width=2, dash=(6, 4))
        self.create_text(w / 2, self.H - 16, fill=C["text_muted"], font=F["caption"], width=w - 40,
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


class App(tk.Tk):
    def __init__(self):
        ui.enable_dpi_awareness()
        super().__init__()
        ui.apply(self)
        self.title("WinNAT UI " + VERSION)
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
        self.refresh()

    # ------------------------------------------------------------ layout --
    def build(self):
        side = tk.Frame(self, bg=C["side_bg"], width=228)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = ttk.Frame(side, style="Side.TFrame")
        brand.pack(fill="x", padx=S4, pady=(S5, S4))
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
        texts.bind("<Configure>", lambda e: (self.cb_title.configure(wraplength=max(200, e.width)),
                                             self.cb_hint.configure(wraplength=max(200, e.width))))
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
        self.wan1 = tk.StringVar(value="USB-C")
        self.wan2 = tk.StringVar(value="Wi-Fi")
        self.wan = self.wan1
        self.prefix = tk.StringVar(value="10.10.10.0/24")
        self.gateway = tk.StringVar(value="10.10.10.1")
        self.profile_nat = tk.StringVar(value="NAT-Firewall")
        self.metric1 = tk.StringVar(value="10")
        self.metric2 = tk.StringVar(value="50")

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
            msg = ttk.Label(form, text=hint, style="Card.Caption.TLabel")
            msg.grid(row=r + 2, column=col, columnspan=span, sticky="w", pady=(2, 0), padx=pad)
            if newrow:
                row[0] += 3
            self.field_errors[key] = (msg, hint)
            self.field_widgets[key] = control
            variable.trace_add("write", lambda *a: self.validate_form())
            return control

        heading("1", "Interfacce")
        self.lan_box = field("lan", "LAN \u2014 verso i client", self.lan, True, "Scheda collegata al firewall o allo switch")
        self.wan_box = field("wan1", "WAN primaria", self.wan1, True, "Gi\u00e0 connessa a Internet", col=0, span=1, newrow=False)
        self.wan2_box = field("wan2", "WAN di riserva", self.wan2, True, "Opzionale", col=1, span=1)
        heading("2", "Indirizzamento LAN")
        field("prefix", "Subnet LAN (CIDR)", self.prefix, hint="Es. 10.10.10.0/24", col=0, span=1, newrow=False)
        field("gateway", "IP del PC sulla LAN", self.gateway, hint="Gateway per i client", col=1, span=1)
        field("nat", "Nome regola NAT", self.profile_nat, hint="Lettere, numeri, - e _")
        heading("3", "Priorit\u00e0 WAN")
        field("metric1", "Metrica primaria", self.metric1, hint="Pi\u00f9 bassa = preferita", col=0, span=1, newrow=False)
        field("metric2", "Metrica di riserva", self.metric2, hint="Maggiore della primaria", col=1, span=1)
        ttk.Button(form, text="Ripristina valori consigliati", style="CardGhost.TButton",
                   command=self.reset_form).grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(S4, 0))

        plan_card = ui.Card(setup, padding=S5)
        plan_card.grid(row=1, column=1, sticky="nsew")
        ttk.Label(plan_card.body, text="COSA SUCCEDER\u00c0 AL COMMIT", style="Card.Overline.TLabel").pack(anchor="w")
        self.plan_list = tk.Frame(plan_card.body, bg=C["surface"])
        self.plan_list.pack(fill="x", pady=(S2, S3))
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

    def reset_form(self):
        d = network_guide.DEFAULTS
        names = [a["Name"] for a in (self.data or {}).get("adapters", [])]
        for var, key in ((self.lan, "lan"), (self.wan1, "wan1"), (self.wan2, "wan2")):
            if not names or d[key] in names:
                var.set(d[key])
        for var, key in ((self.prefix, "prefix"), (self.gateway, "gateway"), (self.profile_nat, "nat"),
                         (self.metric1, "metric1"), (self.metric2, "metric2")):
            var.set(str(d[key]))

    def form_profile(self):
        return {"lan": self.lan.get(), "wan1": self.wan1.get(), "wan2": self.wan2.get(),
                "prefix": self.prefix.get().strip(), "gateway": self.gateway.get().strip(),
                "nat": self.profile_nat.get().strip(), "metric1": self.metric1.get().strip(),
                "metric2": self.metric2.get().strip()}

    def field_problems(self):
        """Inline, per-field validation (error prevention before any PowerShell call)."""
        p, errors = self.form_profile(), {}
        if not p["lan"]:
            errors["lan"] = "Seleziona la scheda LAN."
        if not p["wan1"]:
            errors["wan1"] = "Seleziona la WAN primaria."
        elif p["wan1"] == p["lan"]:
            errors["wan1"] = "Deve essere diversa dalla LAN."
        if p["wan2"] and p["wan2"] in (p["lan"], p["wan1"]):
            errors["wan2"] = "Deve essere diversa da LAN e WAN primaria."
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
        try:
            network.validate_name(p["nat"])
        except ValueError as exc:
            errors["nat"] = str(exc)
        metrics = {}
        for key in ("metric1", "metric2"):
            try:
                metrics[key] = int(p[key])
                if not 1 <= metrics[key] <= 9999:
                    raise ValueError
            except ValueError:
                errors[key] = "Numero intero da 1 a 9999."
        if p["wan2"] and len(metrics) == 2 and metrics["metric1"] >= metrics["metric2"]:
            errors["metric2"] = "Deve essere maggiore della metrica primaria (" + str(metrics["metric1"]) + ")."
        return errors

    def validate_form(self):
        if not hasattr(self, "plan_list"):
            return
        errors = self.field_problems()
        for key, (label, hint) in self.field_errors.items():
            err = errors.get(key)
            label.configure(text="⚠  " + err if err else hint,
                            style="Card.Error.TLabel" if err else "Card.Caption.TLabel")
            widget = self.field_widgets[key]
            if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
                widget.configure(style="Invalid.TEntry" if err else "TEntry")
        for child in self.plan_list.winfo_children():
            child.destroy()
        issue = None
        lines = []
        if self.data is None:
            issue = "Attendi il caricamento della configurazione di rete…"
        elif errors:
            issue = "Da correggere: " + ", ".join(FIELD_TITLES[k] for k in errors if k in FIELD_TITLES) + "."
        else:
            try:
                lines = network_guide.preview("apply", self.form_profile(), self.data)
            except Exception as exc:
                issue = str(exc)
        for i, line in enumerate(l for l in lines if not l.startswith("ATTENZIONE")):
            r = tk.Frame(self.plan_list, bg=C["surface"])
            r.pack(fill="x", pady=1)
            tk.Label(r, text=str(i + 1), font=F["overline"], width=3, bg=C["surface_alt"], fg=C["text_muted"]).pack(side="left", anchor="n", pady=2)
            t = tk.Label(r, text=line, font=F["body"], bg=C["surface"], fg=C["text"], anchor="w", justify="left",
                         wraplength=380)
            t.pack(side="left", fill="x", expand=True, padx=S2)
            t.bind("<Configure>", lambda e, t=t: t.configure(wraplength=max(160, e.width - 4)))
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
        wans = ", ".join(w for w in (self.wan1.get(), self.wan2.get()) if w) or "—"
        self.scope_label.set("Interfacce interessate (dalla scheda Configura):  LAN " + (self.lan.get() or "—")
                             + "   ·   WAN " + wans, "info")

    # ---------------------------------------------------------- changes ---
    def build_changes(self, page):
        ttk.Button(page.actions, text="Scarta tutto", command=self.discard).pack(side="right")
        self.changes_box = ttk.Frame(page)
        self.changes_box.pack(fill="both", expand=True)
        # Kept for compatibility with older code paths (select + unstage).
        self.pending_table = ttk.Treeview(page, columns=("action", "details"), show="headings")
        self.summary = tk.Text(page)

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
        self.section(page, "Scorciatoie da tastiera")
        keys = ui.Card(page, padding=S4)
        keys.pack(fill="x")
        for i, (k, v) in enumerate([("F5", "Aggiorna configurazione"), ("Ctrl + 1 … 6", "Cambia sezione"),
                                    ("Ctrl + Invio", "Applica la modifica in attesa"), ("Canc", "Elimina la regola NAT selezionata"),
                                    ("Ctrl + F", "Filtra le sessioni"), ("Esc", "Chiude le finestre di dialogo")]):
            tk.Label(keys.body, text=k, font=F["mono_s"], bg=C["surface_alt"], fg=C["text"], padx=S2, pady=2).grid(
                row=i, column=0, sticky="w", pady=2)
            tk.Label(keys.body, text=v, font=F["body"], bg=C["surface"], fg=C["text_muted"]).grid(row=i, column=1, sticky="w", padx=S4)

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
    def show_error_dialog(self, title, operation, message, traceback_text="", commit=False):
        """Readable summary first; complete, copyable debug details on demand."""
        dlg = Dialog(self, title, "Chiudi", cancel="Copia tutto")
        dlg.ok.configure(command=dlg.destroy)
        details = format_error_debug(operation, message, traceback_text)

        def copy_all():
            dlg.clipboard_clear()
            dlg.clipboard_append(details)
            dlg.update()
            dlg.cancel_btn.configure(text="Copiato \u2713")
        dlg.cancel_btn.configure(command=copy_all)
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
        viewer.insert("1.0", details)
        viewer.configure(state="disabled")
        viewer.bind("<Control-a>", lambda e: (viewer.tag_add("sel", "1.0", "end-1c"), "break")[1])
        toggle = ttk.Button(dlg.body, text="Mostra dettagli tecnici", style="CardGhost.TButton")

        def toggle_debug():
            if panel.winfo_ismapped():
                panel.pack_forget()
                toggle.configure(text="Mostra dettagli tecnici")
            else:
                panel.pack(fill="both", expand=True, pady=(S2, 0))
                toggle.configure(text="Nascondi dettagli tecnici")
            dlg.recenter()
        toggle.configure(command=toggle_debug)
        toggle.pack(anchor="w", pady=(S3, 0))
        dlg.resizable(True, True)
        dlg.run(focus=dlg.ok)

    def run_task(self, key, fn, on_success):
        if key in self.tasks:
            return
        self.tasks.add(key)
        self.notice.set(key + " in corso…")
        self.progress.start(11)

        def runner():
            try:
                self.work.put((key, True, fn(), on_success))
            except Exception as error:
                self.work.put((key, False, (str(error), traceback.format_exc()), on_success))
        threading.Thread(target=runner, daemon=True).start()
        self.render_changebar()

    def drain(self):
        try:
            while True:
                key, ok, value, callback = self.work.get_nowait()
                self.tasks.discard(key)
                if not self.tasks:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                if ok:
                    callback(value)
                else:
                    error_message, error_traceback = value
                    self.notice.set("Errore: " + error_summary(error_message)[:80])
                    if key == "Commit":
                        # The script is not transactional: the previous steps may
                        # already have changed Windows even though one step failed.
                        # Do not allow a stale candidate to be re-committed.
                        self.pending.clear()
                        self.render_candidate()
                        self.show_error_dialog("Commit non riuscito", key,
                                               error_message, error_traceback, commit=True)
                        self.refresh()
                    else:
                        self.show_error_dialog("Operazione non riuscita", key, error_message, error_traceback)
                self.render_changebar()
        except queue.Empty:
            pass
        self.after(100, self.drain)

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
        self.wan2_box["values"] = [""] + adapter_names
        if self.wan2.get() not in adapter_names:
            self.wan2.set("Wi-Fi" if "Wi-Fi" in adapter_names else "")
        self.wan_box["values"] = adapter_names
        if adapter_names and self.lan.get() not in adapter_names:
            self.lan.set("Ethernet" if "Ethernet" in adapter_names else adapter_names[0])
        routes = self.default_routes()
        if routes and (not self.wan1.get() or self.wan1.get() not in adapter_names):
            self.wan.set(routes[0].get("InterfaceAlias", ""))

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

        lan, wans = self.lan.get(), [self.wan1.get(), self.wan2.get()]
        default_alias = routes[0].get("InterfaceAlias") if routes else None
        t = self.iface_table
        t.delete(*t.get_children())
        for i, a in enumerate(data.get("adapters", [])):
            name = a.get("Name")
            ips = ", ".join(f"{p['IPAddress']}/{p['PrefixLength']}" for p in data.get("ips", [])
                            if p.get("InterfaceIndex") == a.get("InterfaceIndex")) or "—"
            info = ifaces.get(name, {})
            role = "LAN" if name == lan else ("WAN 1" if name == wans[0] else "WAN 2" if name and name == wans[1] else "")
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
        removals = {p["args"][0] for p in self.pending if p["kind"] == "remove"}
        for name, n in nats.items():
            self.nat_table.insert("", "end", values=("- Da eliminare" if name in removals else "Applicata", name,
                                                     n.get("InternalIPInterfaceAddressPrefix", ""), yes_no(n.get("Active"))))
        for p in self.pending:
            if p["kind"] == "guide":
                act, profile, _fingerprint = p["args"]
                if act == "apply":
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
                hint = "Verrà salvato uno snapshot JSON prima dell'applicazione (non è un rollback automatico)."
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
        self.pending.append(dict(kind=kind, args=args, label=label, details=details))
        self.render_candidate()
        self.toast.show("«" + label + "» aggiunta alle modifiche in attesa.", "info")

    def add(self):
        if self.data is None:
            return self.toast.show("Attendi il caricamento della configurazione.", "warning")
        dlg = Dialog(self, "Aggiungi regola NAT", "Aggiungi alle modifiche")
        name, prefix = tk.StringVar(value="WinNAT-UI"), tk.StringVar(value="192.168.1.0/24")
        if self.data.get("nats"):
            ui.Callout(dlg.body, kind="warning", wraplength=380,
                       text="Esiste già una regola WinNAT: Windows supporta un solo prefisso interno e il commit verrà bloccato.").pack(fill="x", pady=(0, S3))
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
            self.stage("add", (n, pfx), "Aggiungi NAT", n + " / " + pfx)

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
        plan = {"lan": lan, "wan": self.wan.get(), "prefix": prefix, "gateway": gateway}
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
            # Not an atomic transaction: a failure keeps remaining operations candidate.
            current = network.collect()
            backup_path = network.snapshot(current)
            completed = []
            for p in changes:
                kind, args = p["kind"], p["args"]
                scope = network_rollback.scope_for(kind, args, current)
                try:
                    nats = current.get("nats", [])
                    if kind == "add":
                        if nats or any(c.get("SharingEnabled") for c in current.get("icsConnections", [])):
                            raise ValueError("WinNAT/ICS presente: rimuovi prima la configurazione concorrente.")
                        network.create_nat(*args)
                    elif kind == "remove":
                        if not any(n.get("Name") == args[0] for n in nats):
                            raise ValueError("NAT non presente: " + args[0])
                        network.remove_nat(*args)
                    elif kind == "setup":
                        if nats or any(c.get("SharingEnabled") for c in current.get("icsConnections", [])):
                            raise ValueError("Setup bloccato da WinNAT/ICS esistente.")
                        network.setup(*args, current)
                    elif kind == "guide":
                        network_guide.execute(args[0], args[1], current, args[2])
                    elif kind == "profile":
                        network_plan.apply_profile(args[0], current)
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
                    current = network.collect()
                except Exception as original:
                    try:
                        report = network_rollback.rollback(current, scope, backup_path)
                    except Exception as rollback_error:
                        raise RuntimeError(
                            "COMMIT FALLITO: " + str(original) + "\\n\\n"
                            "ROLLBACK INCOMPLETO O NON VERIFICABILE:\\n" + str(rollback_error)
                            + "\\nSnapshot: " + str(backup_path)) from original
                    raise RuntimeError(
                        "COMMIT FALLITO: " + str(original) + "\\n\\n" + report
                        + "\\nSnapshot: " + str(backup_path)) from original
            return completed

        def success(applied):
            self.pending = [p for p in self.pending if p not in applied]
            self.render_candidate()
            router_changed = any(p["kind"] == "guide" for p in applied)
            self.toast.show("Modifica applicata." + (" Riavvia Windows prima dei test end-to-end: "
                                                    "IPEnableRouter è cambiato." if router_changed else ""),
                            "success", ms=9000 if router_changed else 4000)
            self.refresh()
        self.run_task("Commit", execute, success)

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
