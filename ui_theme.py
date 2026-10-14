"""WinNAT UI design system: tokens, ttk styles and small reusable widgets.

Pure Tkinter/ttk (no third-party packages) so the PyInstaller build and the
Defender gate stay unchanged. Colours follow the Windows light/dark setting.
"""
import sys
import tkinter as tk
from tkinter import ttk, font as tkfont

# ---------------------------------------------------------------- tokens ---
# 8 px spacing grid: every padding/margin in the app is a multiple of SPACE.
SPACE = 8
S1, S2, S3, S4, S5 = 4, 8, 12, 16, 24

LIGHT = dict(
    bg="#F3F5F9",            # page background
    surface="#FFFFFF",       # cards, tables, inputs
    surface_alt="#F7F9FC",   # zebra rows, quiet panels
    border="#DDE3EC",
    border_strong="#C3CCD9",
    text="#152033",
    text_muted="#5B6778",
    text_faint="#8792A2",
    accent="#0E7C86",        # teal: "network/link" identity colour
    accent_hover="#0B6A73",
    accent_soft="#E3F3F4",
    accent_text="#FFFFFF",
    success="#1B7F4B", success_soft="#E4F4EA",
    warning="#A15C00", warning_soft="#FFF3DC",
    danger="#B3261E", danger_soft="#FCE8E6",
    info="#2457C5", info_soft="#E6EEFC",
    side_bg="#0F1B2D", side_hover="#1A2A42", side_active="#22375A",
    side_text="#C9D3E3", side_muted="#7D8BA3", side_accent="#38C6CF",
    select="#CFE9EB",
)

DARK = dict(
    bg="#121821", surface="#1A222E", surface_alt="#1F2835",
    border="#2C3746", border_strong="#3A4759",
    text="#E6EBF2", text_muted="#A3AEBE", text_faint="#748094",
    accent="#2BB3BD", accent_hover="#45C4CD", accent_soft="#173A3F", accent_text="#071518",
    success="#4CC38A", success_soft="#163327",
    warning="#E3A33B", warning_soft="#3A2C14",
    danger="#F2766B", danger_soft="#3D1D1B",
    info="#7AA2F7", info_soft="#1C2A47",
    side_bg="#0B1119", side_hover="#152030", side_active="#1D2C42",
    side_text="#C9D3E3", side_muted="#6F7C92", side_accent="#38C6CF",
    select="#1E4A50",
)

C = dict(LIGHT)   # active palette, filled by apply()
F = {}            # named fonts, filled by apply()
ICON_FONT = None

# Segoe Fluent Icons (Win 11) / Segoe MDL2 Assets (Win 10) code points with a
# plain Unicode fallback, so the UI never shows empty squares.
ICONS = {
    "dashboard": ("", "⌂"),
    "nat": ("", "⇄"),
    "network": ("", "◈"),
    "changes": ("", "✎"),
    "sessions": ("", "≡"),
    "info": ("", "ⓘ"),
    "refresh": ("", "↻"),
    "add": ("", "+"),
    "delete": ("", "✕"),
    "save": ("", "↓"),
    "warning": ("", "⚠"),
    "ok": ("", "✓"),
    "shield": ("", "⛨"),
    "search": ("", "⌕"),
}


def icon(name):
    glyph, fallback = ICONS[name]
    return glyph if ICON_FONT else fallback


def system_dark():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def enable_dpi_awareness():
    """Crisp text on high-DPI screens (must run before the Tk root exists)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _pick(families, *candidates):
    for name in candidates:
        if name in families:
            return name
    return "TkDefaultFont"


def apply(root, dark=None):
    """Install palette, fonts and every ttk style used by the app."""
    global ICON_FONT
    C.clear()
    C.update(DARK if (system_dark() if dark is None else dark) else LIGHT)
    families = set(tkfont.families(root))
    ui = _pick(families, "Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans")
    display = _pick(families, "Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", "Inter Display", ui)
    mono = _pick(families, "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "TkFixedFont")
    ICON_FONT = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)

    # Type scale (pt): 9 caption / 10 body / 11 strong / 14 title / 20 display.
    F.update(
        caption=(ui, 9), body=(ui, 10), body_b=(ui, 10, "bold"), strong=(ui, 11, "bold"),
        title=(display, 15, "bold"), display=(display, 20, "bold"), kpi=(display, 17, "bold"),
        overline=(ui, 8, "bold"), mono=(mono, 10), mono_s=(mono, 9),
        icon=((ICON_FONT or ui), 12), icon_l=((ICON_FONT or ui), 18),
    )
    tkfont.nametofont("TkDefaultFont").configure(family=ui, size=10)
    tkfont.nametofont("TkTextFont").configure(family=ui, size=10)

    root.configure(bg=C["bg"])
    root.option_add("*TCombobox*Listbox.background", C["surface"])
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", C["accent_text"])
    root.option_add("*TCombobox*Listbox.font", F["body"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=C["bg"], foreground=C["text"], font=F["body"],
                bordercolor=C["border"], lightcolor=C["surface"], darkcolor=C["surface"],
                troughcolor=C["bg"], focuscolor=C["accent"], selectbackground=C["accent"],
                selectforeground=C["accent_text"], insertcolor=C["text"])

    # Labels: one style per surface + semantic role.
    for surface, bg in (("", C["bg"]), ("Card.", C["surface"]), ("Side.", C["side_bg"])):
        fg = C["side_text"] if surface == "Side." else C["text"]
        muted = C["side_muted"] if surface == "Side." else C["text_muted"]
        s.configure(surface + "TLabel", background=bg, foreground=fg)
        s.configure(surface + "Muted.TLabel", background=bg, foreground=muted)
        s.configure(surface + "Caption.TLabel", background=bg, foreground=muted, font=F["caption"])
        s.configure(surface + "Overline.TLabel", background=bg, foreground=muted, font=F["overline"])
        s.configure(surface + "Strong.TLabel", background=bg, foreground=fg, font=F["strong"])
        s.configure(surface + "Title.TLabel", background=bg, foreground=fg, font=F["title"])
        s.configure(surface + "Display.TLabel", background=bg, foreground=fg, font=F["display"])
        s.configure(surface + "Error.TLabel", background=bg, foreground=C["danger"], font=F["caption"])
        s.configure(surface + "Ok.TLabel", background=bg, foreground=C["success"], font=F["caption"])
        s.configure(surface + "TFrame", background=bg)
        s.configure(surface + "TCheckbutton", background=bg, foreground=fg,
                    indicatorbackground=C["surface"], indicatorforeground=C["accent"])
        s.map(surface + "TCheckbutton", background=[("active", bg)],
              indicatorbackground=[("selected", C["accent_soft"])])
        s.configure(surface + "TRadiobutton", background=bg, foreground=fg)
        s.map(surface + "TRadiobutton", background=[("active", bg)])
    s.configure("Side.Brand.TLabel", background=C["side_bg"], foreground="#FFFFFF", font=F["title"])
    s.configure("Side.Logo.TLabel", background=C["side_bg"], foreground=C["side_accent"], font=F["icon_l"])

    # Buttons: secondary (default), primary accent, danger, ghost, nav.
    pad = (S4, 7)
    s.configure("TButton", background=C["surface"], foreground=C["text"], padding=pad,
                bordercolor=C["border_strong"], lightcolor=C["surface"], darkcolor=C["surface"],
                relief="solid", borderwidth=1, focusthickness=1, focuscolor=C["accent"])
    s.map("TButton",
          background=[("disabled", C["surface_alt"]), ("pressed", C["border"]), ("active", C["surface_alt"])],
          foreground=[("disabled", C["text_faint"])],
          bordercolor=[("focus", C["accent"]), ("active", C["border_strong"])])
    for name, base, hover, fg in (("Accent", C["accent"], C["accent_hover"], C["accent_text"]),
                                  ("Danger", C["danger"], C["danger"], "#FFFFFF")):
        s.configure(name + ".TButton", background=base, foreground=fg, bordercolor=base,
                    lightcolor=base, darkcolor=base, font=F["body_b"], padding=pad)
        s.map(name + ".TButton",
              background=[("disabled", C["border"]), ("pressed", hover), ("active", hover)],
              foreground=[("disabled", C["text_faint"])],
              bordercolor=[("disabled", C["border"]), ("focus", C["text"]), ("active", hover)],
              lightcolor=[("active", hover)], darkcolor=[("active", hover)])
    s.configure("Ghost.TButton", background=C["bg"], bordercolor=C["bg"], lightcolor=C["bg"],
                darkcolor=C["bg"], foreground=C["accent"], padding=(S2, 5))
    s.map("Ghost.TButton", background=[("active", C["accent_soft"])],
          bordercolor=[("focus", C["accent"]), ("active", C["accent_soft"])])
    s.configure("CardGhost.TButton", background=C["surface"], bordercolor=C["surface"],
                lightcolor=C["surface"], darkcolor=C["surface"], foreground=C["accent"], padding=(S2, 4))
    s.map("CardGhost.TButton", background=[("active", C["accent_soft"])],
          bordercolor=[("focus", C["accent"]), ("active", C["accent_soft"])],
          foreground=[("disabled", C["text_faint"])])
    for state, bg, fg in (("Nav", C["side_bg"], C["side_text"]), ("NavActive", C["side_active"], "#FFFFFF")):
        s.configure(state + ".TButton", background=bg, foreground=fg, bordercolor=bg,
                    lightcolor=bg, darkcolor=bg, anchor="w", padding=(S3, 9),
                    font=F["body_b"] if state == "NavActive" else F["body"])
        s.map(state + ".TButton", background=[("active", C["side_hover"] if state == "Nav" else bg)],
              bordercolor=[("focus", C["side_accent"]), ("active", C["side_hover"] if state == "Nav" else bg)])
    s.configure("Seg.TButton", background=C["surface"], foreground=C["text_muted"], padding=(S4, 6),
                bordercolor=C["border"])
    s.configure("SegActive.TButton", background=C["accent_soft"], foreground=C["accent"], padding=(S4, 6),
                bordercolor=C["accent"], font=F["body_b"])
    s.map("Seg.TButton", background=[("active", C["surface_alt"])])
    s.map("SegActive.TButton", background=[("active", C["accent_soft"])])

    # Inputs.
    for name, border in (("TEntry", C["border_strong"]), ("Invalid.TEntry", C["danger"])):
        s.configure(name, fieldbackground=C["surface"], foreground=C["text"], padding=(S2, 6),
                    bordercolor=border, lightcolor=C["surface"], darkcolor=C["surface"],
                    insertcolor=C["text"])
        s.map(name, bordercolor=[("focus", C["danger"] if "Invalid" in name else C["accent"])],
              lightcolor=[("focus", C["danger"] if "Invalid" in name else C["accent"])])
    s.configure("TCombobox", fieldbackground=C["surface"], background=C["surface"], foreground=C["text"],
                arrowcolor=C["text_muted"], bordercolor=C["border_strong"], lightcolor=C["surface"],
                darkcolor=C["surface"], padding=(S2, 5))
    s.map("TCombobox", fieldbackground=[("readonly", C["surface"])],
          foreground=[("readonly", C["text"])], selectbackground=[("readonly", C["surface"])],
          selectforeground=[("readonly", C["text"])],
          bordercolor=[("focus", C["accent"]), ("active", C["accent"])],
          background=[("active", C["surface_alt"])])

    # Tables.
    s.configure("Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["text"],
                rowheight=30, borderwidth=0, bordercolor=C["border"], lightcolor=C["surface"],
                darkcolor=C["surface"], font=F["body"])
    s.map("Treeview", background=[("selected", C["select"])], foreground=[("selected", C["text"])])
    s.configure("Treeview.Heading", background=C["surface_alt"], foreground=C["text_muted"],
                font=F["overline"], relief="flat", padding=(S2, 7), bordercolor=C["border"],
                lightcolor=C["surface_alt"], darkcolor=C["surface_alt"])
    s.map("Treeview.Heading", background=[("active", C["border"])])
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    for orient in ("Vertical", "Horizontal"):
        s.configure(orient + ".TScrollbar", background=C["border"], troughcolor=C["surface"],
                    bordercolor=C["surface"], lightcolor=C["border"], darkcolor=C["border"],
                    arrowcolor=C["text_muted"], gripcount=0, arrowsize=11)
        s.map(orient + ".TScrollbar", background=[("active", C["border_strong"])])
    s.configure("Thin.Horizontal.TProgressbar", troughcolor=C["bg"], background=C["accent"],
                bordercolor=C["bg"], lightcolor=C["accent"], darkcolor=C["accent"], thickness=3)
    s.configure("TSeparator", background=C["border"])
    s.configure("Side.TSeparator", background=C["side_hover"])
    return s


# ------------------------------------------------------------- widgets ---
class Card(tk.Frame):
    """White surface with a 1 px border; optional coloured left edge for severity."""

    def __init__(self, parent, edge=None, padding=S4, bg=None, **kw):
        super().__init__(parent, bg=bg or C["surface"], highlightthickness=1,
                         highlightbackground=C["border"], highlightcolor=C["border"], **kw)
        if edge:
            tk.Frame(self, bg=edge, width=4).pack(side="left", fill="y")
        self.body = tk.Frame(self, bg=bg or C["surface"])
        self.body.pack(side="left", fill="both", expand=True, padx=padding, pady=padding)


class Badge(tk.Label):
    """Pill with text + symbol, so status never relies on colour alone."""
    KINDS = {"success": ("success", "success_soft"), "warning": ("warning", "warning_soft"),
             "danger": ("danger", "danger_soft"), "info": ("info", "info_soft"),
             "neutral": ("text_muted", "surface_alt"), "accent": ("accent", "accent_soft")}

    def __init__(self, parent, text="", kind="neutral", **kw):
        super().__init__(parent, font=F["overline"], padx=S2, pady=2, bd=0, **kw)
        self.set(text, kind)

    def set(self, text, kind="neutral"):
        fg, bg = self.KINDS.get(kind, self.KINDS["neutral"])
        self.configure(text=text, fg=C[fg], bg=C[bg])


class Callout(tk.Frame):
    """Inline message (info / warning / danger / success) with an icon."""

    def __init__(self, parent, text="", kind="info", wraplength=760, **kw):
        super().__init__(parent, bd=0, **kw)
        self.icon = tk.Label(self, font=F["icon"], bd=0)
        self.icon.pack(side="left", anchor="n", padx=(S3, S2), pady=S2)
        self.label = tk.Label(self, justify="left", anchor="w", font=F["body"], wraplength=wraplength, bd=0)
        self.label.pack(side="left", fill="x", expand=True, pady=S2, padx=(0, S3))
        # Wrap to the available width instead of a fixed pixel count.
        self.bind("<Configure>", lambda e: self.label.configure(wraplength=max(160, e.width - 64)))
        self.set(text, kind)

    def set(self, text, kind="info"):
        fg, soft = C[kind], C[kind + "_soft"]
        glyph = icon({"info": "info", "warning": "warning", "danger": "warning", "success": "ok"}[kind])
        self.configure(bg=soft)
        self.icon.configure(text=glyph, fg=fg, bg=soft)
        self.label.configure(text=text, fg=C["text"], bg=soft)


class ScrollFrame(ttk.Frame):
    """Vertically scrollable page; `.inner` is where content goes."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))

    def _on_scroll(self, first, last):
        self.bar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")

    def _wheel(self, event):
        if self.bar.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), "units")


class Toast:
    """Non-blocking feedback in the bottom-right corner; auto-dismisses."""

    def __init__(self, root):
        self.root = root
        self.frame = None
        self.job = None

    def show(self, text, kind="success", ms=3800):
        self.hide()
        fg = C[kind]
        frame = tk.Frame(self.root, bg=C["surface"], highlightthickness=1, highlightbackground=C["border_strong"])
        tk.Frame(frame, bg=fg, width=4).pack(side="left", fill="y")
        tk.Label(frame, text=icon({"success": "ok", "info": "info"}.get(kind, "warning")), font=F["icon"],
                 fg=fg, bg=C["surface"]).pack(side="left", padx=(S3, S2), pady=S3)
        tk.Label(frame, text=text, font=F["body"], fg=C["text"], bg=C["surface"], wraplength=360,
                 justify="left").pack(side="left", padx=(0, S4), pady=S3)
        frame.place(relx=1.0, rely=1.0, x=-S5, y=-84, anchor="se")
        frame.bind("<Button-1>", lambda e: self.hide())
        self.frame = frame
        self.job = self.root.after(ms, self.hide)

    def hide(self):
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.frame:
            self.frame.destroy()
            self.frame = None


def make_table(parent, columns, height=10):
    """Treeview inside a bordered card with zebra-ready tags and a scrollbar."""
    wrap = tk.Frame(parent, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
    view = ttk.Treeview(wrap, columns=[c[0] for c in columns], show="headings", height=height)
    for code, label, width, *rest in columns:
        view.heading(code, text=label.upper(), anchor="w")
        view.column(code, width=width, minwidth=60, anchor="w", stretch=bool(rest[0]) if rest else True)
    bar = ttk.Scrollbar(wrap, orient="vertical", command=view.yview)

    def autohide(first, last):
        bar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            bar.pack_forget()
        elif not bar.winfo_ismapped():
            bar.pack(side="right", fill="y", before=view)
    view.configure(yscrollcommand=autohide)
    view.pack(side="left", fill="both", expand=True)
    view.tag_configure("odd", background=C["surface_alt"])
    view.tag_configure("add", background=C["success_soft"], foreground=C["success"])
    view.tag_configure("remove", background=C["danger_soft"], foreground=C["danger"])
    view.tag_configure("muted", foreground=C["text_faint"])
    wrap.view = view
    return wrap, view
