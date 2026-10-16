"""Collaudo Windows per Issue #65 sulla build CI (EXE PyInstaller).

Ogni scenario avvia WinNAT-UI.exe in un ambiente controllato, attende la
sincronizzazione silenziosa all'avvio, poi (se note le coordinate) preme
"Verifica stato Issue" e raccoglie: finestre aperte dal processo (titolo e
testo), reattivita' della finestra, cronologia locale prima/dopo, istantanea
della configurazione di rete prima/dopo, screenshot.

Le simulazioni sono limitate al processo (variabili proxy) o a una regola
firewall in uscita sul solo eseguibile: nessuna modifica a NAT, IP, DNS o
forwarding del sistema.
"""
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop
from pywinauto.keyboard import send_keys
import pywinauto.mouse as mouse

EXE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
CLICK = os.environ.get("ISSUE_BUTTON_XY")  # "x,y" relativo alla finestra 1200x800
OUT.mkdir(parents=True, exist_ok=True)
STORE = Path(os.environ["LOCALAPPDATA"]) / "WinNAT-UI" / "reported-issues.json"
REPO = "matiz311/WinNAT-UI"

SEED = [
    {"fingerprint": "78526215de513c2be66d6b80", "number": 65,
     "url": "https://github.com/" + REPO + "/issues/65", "operation": "Stato bug",
     "category": "Errore operativo non classificato", "version": "1.15.0",
     "reported_at": "2026-10-16T21:26:09+00:00",
     # Stato volutamente errato: una sync riuscita lo porta a "open".
     "state": "closed", "fixed_in": None},
    {"fingerprint": "000000000000000000000000", "number": 99999,
     "url": "https://github.com/" + REPO + "/issues/99999", "operation": "Collaudo",
     "category": "Voce solo locale", "version": "1.15.1",
     "reported_at": "2026-10-17T00:00:00+00:00", "state": "open", "fixed_in": None},
]

PS_SNAPSHOT = r"""
$ErrorActionPreference='SilentlyContinue'
[ordered]@{
 nat = @(Get-NetNat | Select Name,InternalIPInterfaceAddressPrefix,Active)
 ips = @(Get-NetIPAddress -AddressFamily IPv4 | Select InterfaceAlias,IPAddress,PrefixLength,PrefixOrigin | Sort InterfaceAlias,IPAddress)
 routes = @(Get-NetRoute -AddressFamily IPv4 | Select InterfaceAlias,DestinationPrefix,NextHop,RouteMetric | Sort InterfaceAlias,DestinationPrefix,NextHop)
 dns = @(Get-DnsClientServerAddress -AddressFamily IPv4 | Select InterfaceAlias,@{n='S';e={$_.ServerAddresses -join ','}} | Sort InterfaceAlias)
 fwd = @(Get-NetIPInterface -AddressFamily IPv4 | Select InterfaceAlias,Forwarding | Sort InterfaceAlias)
 ics = (Get-Service SharedAccess).Status.ToString()
} | ConvertTo-Json -Depth 4 -Compress
"""


def ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script],
                          capture_output=True, text=True, timeout=120)


def snapshot():
    return json.loads(ps(PS_SNAPSHOT).stdout or "{}")


def store_bytes():
    return STORE.read_bytes() if STORE.exists() else b""


def bug_report_count():
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/issues?state=all&labels=bug-report&per_page=100" % REPO,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return len(json.load(r))


user32 = ctypes.windll.user32


def responsive(hwnd, ms=3000):
    res = ctypes.c_size_t()
    ok = user32.SendMessageTimeoutW(wintypes.HWND(hwnd), 0, 0, 0, 0x0002, ms, ctypes.byref(res))
    return bool(ok)


def windows_of(pid):
    found = []
    for w in Desktop(backend="win32").windows(process=pid, visible_only=True):
        try:
            texts = [c.window_text() for c in w.descendants() if c.window_text()]
        except Exception:
            texts = []
        found.append({"title": w.window_text(), "class": w.class_name(), "texts": texts,
                      "handle": w.handle})
    return found


def main_window(pid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        for w in Desktop(backend="win32").windows(process=pid, visible_only=True):
            if w.class_name() == "TkTopLevel" and "WinNAT" in w.window_text():
                return w
        time.sleep(1)
    raise RuntimeError("Finestra principale non trovata")


def shot(name, hwnd=None):
    path = OUT / (name + ".png")
    if hwnd:
        r = wintypes.RECT()
        user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r))
        ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True).save(path)
    else:
        ImageGrab.grab(all_screens=True).save(path)
    return path.name


def tk_children(hwnd):
    """Tk crea un HWND figlio per ogni widget: utile per localizzare il pulsante."""
    out = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    top = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(top))

    def cb(h, _):
        if user32.IsWindowVisible(h):
            r = wintypes.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            out.append([r.left - top.left, r.top - top.top, r.right - r.left, r.bottom - r.top])
        return True
    user32.EnumChildWindows(wintypes.HWND(hwnd), EnumProc(cb), 0)
    return out


def scenario(name, env_extra=None, firewall=False, wait_manual=45):
    print("=== " + name, flush=True)
    rec = {"scenario": name}
    before_store = store_bytes()
    before_net = snapshot()
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"):
        env.pop(k, None)
    env.update(env_extra or {})
    if firewall:
        r = ps("New-NetFirewallRule -DisplayName collaudo65 -Direction Outbound -Program '%s' "
               "-Action Block | Out-Null; (Get-NetFirewallProfile | ? Enabled).Name -join ','" % EXE)
        rec["firewall_profiles_enabled"] = r.stdout.strip()
    proc = subprocess.Popen([str(EXE)], env=env, cwd=str(EXE.parent))
    try:
        win = main_window(proc.pid)
        hwnd = win.handle
        user32.MoveWindow(wintypes.HWND(hwnd), 0, 0, 1200, 800, True)
        win.set_focus()
        time.sleep(1)
        send_keys("^6")
        # Sync silenziosa all'avvio a 7 s, timeout richiesta 10 s (+ release_info).
        samples = []
        for _ in range(16):
            time.sleep(2)
            samples.append(responsive(hwnd))
        rec["silent_responsive_samples"] = samples
        rec["silent_windows"] = [w for w in windows_of(proc.pid) if w["handle"] != hwnd]
        rec["silent_shot"] = shot(name + "-1-avvio", hwnd)
        rec["silent_store_unchanged"] = store_bytes() == before_store
        rec["silent_store"] = json.loads(store_bytes() or b"[]")
        if name == "00-scoperta":
            rec["tk_children"] = tk_children(hwnd)
        if CLICK:
            x, y = map(int, CLICK.split(","))
            win.set_focus()
            r = wintypes.RECT()
            user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r))
            mouse.click(coords=(r.left + x, r.top + y))
            t0 = time.time()
            samples, dialogs = [], []
            while time.time() - t0 < wait_manual:
                time.sleep(1.5)
                samples.append(responsive(hwnd))
                dialogs = [w for w in windows_of(proc.pid) if w["handle"] != hwnd]
                if dialogs:
                    break
            rec["manual_seconds"] = round(time.time() - t0, 1)
            rec["manual_responsive_samples"] = samples
            time.sleep(1.5)
            rec["manual_windows"] = [w for w in windows_of(proc.pid) if w["handle"] != hwnd]
            rec["manual_shot"] = shot(name + "-2-verifica", None)
            for d in rec["manual_windows"]:
                if d["class"] == "#32770":
                    Desktop(backend="win32").window(handle=d["handle"]).type_keys("{ENTER}")
            time.sleep(1)
            rec["after_dialog_responsive"] = responsive(hwnd)
        rec["store_unchanged"] = store_bytes() == before_store
        rec["store_after"] = json.loads(store_bytes() or b"[]")
        rec["process_alive"] = proc.poll() is None
    except Exception as exc:
        rec["harness_error"] = repr(exc)
        try:
            rec["error_shot"] = shot(name + "-errore")
        except Exception:
            pass
    finally:
        proc.kill()
        proc.wait(10)
        if firewall:
            ps("Remove-NetFirewallRule -DisplayName collaudo65")
    after_net = snapshot()
    rec["network_unchanged"] = after_net == before_net
    if not rec["network_unchanged"]:
        rec["network_before"], rec["network_after"] = before_net, after_net
    for d in rec.get("silent_windows", []) + rec.get("manual_windows", []):
        d.pop("handle", None)
    return rec


def seed():
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(SEED, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    exe_info = ps("(Get-Item '%s').VersionInfo | Select FileVersion,ProductVersion,ProductName | ConvertTo-Json" % EXE)
    report = {"exe": str(EXE), "exe_sha256": hashlib.sha256(EXE.read_bytes()).hexdigest(),
              "exe_version": json.loads(exe_info.stdout or "{}"),
              "windows": ps("(Get-CimInstance Win32_OperatingSystem | Select Caption,Version,BuildNumber | ConvertTo-Json)").stdout,
              "build_commit": os.environ.get("BUILD_COMMIT"), "build_run": os.environ.get("BUILD_RUN"),
              "click": CLICK, "bug_reports_before": bug_report_count(), "scenarios": []}
    plan = [("00-scoperta", None, False)] if os.environ.get("DISCOVERY") else [
        ("01-online", None, False),
        ("02-dns-proxy-inesistente", {"HTTPS_PROXY": "http://winnat-collaudo.invalid:8080",
                                      "HTTP_PROXY": "http://winnat-collaudo.invalid:8080"}, False),
        ("03-irraggiungibile-porta-chiusa", {"HTTPS_PROXY": "http://127.0.0.1:9",
                                             "HTTP_PROXY": "http://127.0.0.1:9"}, False),
        ("04-timeout-blackhole", {"HTTPS_PROXY": "http://10.255.255.1:3128",
                                  "HTTP_PROXY": "http://10.255.255.1:3128"}, False),
        ("05-firewall-uscita-bloccata", None, True),
        ("06-ripristino-online", None, False),
    ]
    for name, env_extra, firewall in plan:
        seed()
        report["scenarios"].append(scenario(name, env_extra, firewall))
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["bug_reports_after"] = bug_report_count()
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
