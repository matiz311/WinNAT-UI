"""Read-only comparative Windows networking diagnostics for VPN/WinNAT issue #76.

No automatic publication: user reviews and manually attaches the report to GitHub.
Snapshots are collected before setup, after setup and after rollback. Commands
only query system state; nothing changes interfaces, NAT objects or VPN state.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import network

ISSUE_URL = "https://github.com/matiz311/WinNAT-UI/issues/76"
PHASES = ("before", "winnat", "rollback")
PHASE_LABELS = {
    "before": "Prima del setup WinNAT (VPN funzionante)",
    "winnat": "Dopo il setup WinNAT (VPN non connessa)",
    "rollback": "Dopo la rimozione WinNAT (VPN funzionante)",
}
SECTIONS = ("adapters", "interfaces", "addresses", "routes", "nats",
            "dns", "globalRouter", "vpnServices")
MAX_OUTPUT = 512_000
PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
function Grab([scriptblock] $query) {
    try { return @{ ok = $true; rows = @(& $query) } }
    catch { return @{ ok = $false; rows = @(); error = $_.Exception.Message } }
}
$r = [ordered]@{}
$r.adapters = Grab {
    Get-NetAdapter -IncludeHidden -ErrorAction Stop |
        Select-Object Name, InterfaceIndex, InterfaceDescription, Status, MediaType
}
$r.interfaces = Grab {
    Get-NetIPInterface -AddressFamily IPv4 -ErrorAction Stop |
        Select-Object InterfaceAlias, InterfaceIndex, Forwarding, Dhcp,
            AutomaticMetric, InterfaceMetric, ConnectionState, NlMtu
}
$r.addresses = Grab {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Select-Object InterfaceAlias, InterfaceIndex, IPAddress,
            PrefixLength, PrefixOrigin, AddressState
}
$r.routes = Grab {
    Get-NetRoute -AddressFamily IPv4 -ErrorAction Stop |
        Select-Object InterfaceAlias, InterfaceIndex, DestinationPrefix,
            NextHop, RouteMetric, InterfaceMetric, Protocol
}
$r.nats = Grab {
    Get-NetNat -ErrorAction Stop |
        Select-Object Name, InternalIPInterfaceAddressPrefix,
            ExternalIPInterfaceAddressPrefix, Active
}
$r.dns = Grab {
    Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction Stop |
        Select-Object InterfaceAlias, ServerAddresses
}
$r.globalRouter = Grab {
    Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name IPEnableRouter -ErrorAction Stop |
        Select-Object IPEnableRouter
}
$r.vpnServices = Grab {
    Get-Service -ErrorAction Stop |
        Where-Object { $_.Name -match 'Malwarebytes|MBAM|VPN' -or $_.DisplayName -match 'Malwarebytes' } |
        Select-Object Name, DisplayName, Status, StartType
}
$r | ConvertTo-Json -Depth 8 -Compress
"""



def suggest_phase(inventory, snapshots=None):
    """Suggest a phase from cached state, without treating it as proof.

    The UI asks for explicit confirmation. A WinNAT object may belong to
    another component and a connected adapter need not mean an active VPN.
    """
    snapshots = snapshots or {}
    nats = inventory.get("nats") if isinstance(inventory, dict) else None
    if isinstance(nats, list) and nats:
        return "winnat"
    if "before" in snapshots and "winnat" in snapshots:
        return "rollback"
    return "before"

def storage_path():
    folder = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(folder) / "WinNAT-UI" / "vpn-diagnostics.json"


def read(path=None):
    """Load the locally stored state without trusting missing/corrupt content."""
    target = Path(path) if path is not None else storage_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema": 1, "issue": 76, "snapshots": {}}
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("snapshots"), dict):
        raise ValueError("Archivio diagnostico non valido. Esportare la copia precedente prima di continuare.")
    return data


def capture(phase, runner=None, path=None):
    """Capture a named phase; retain independent command failures as evidence."""
    if phase not in PHASES:
        raise ValueError("Fase VPN non valida.")
    execute = runner or network.ps
    raw = execute(PS_SCRIPT)
    if not isinstance(raw, str) or len(raw) > MAX_OUTPUT:
        raise ValueError("Output diagnostico non valido o eccessivo.")
    sections = json.loads(raw)
    if not isinstance(sections, dict):
        raise ValueError("Le sezioni diagnostiche non sono valide.")
    result = {}
    for name in SECTIONS:
        obj = sections.get(name, {})
        if not isinstance(obj, dict) or not isinstance(obj.get("ok"), bool):
            result[name] = {"ok": False, "rows": [], "error": "Sezione non restituita"}
            continue
        rows = obj.get("rows", [])
        if not isinstance(rows, list):
            rows = [rows] if rows is not None else []
        result[name] = {"ok": obj["ok"], "rows": rows}
        if not obj["ok"]:
            result[name]["error"] = str(obj.get("error", "Comando non riuscito"))[:500]
    snapshot = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "sections": result,
    }
    store = read(path)
    store["snapshots"][phase] = snapshot
    target = Path(path) if path is not None else storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return snapshot


def _stable_rows(section):
    if not isinstance(section, dict):
        return []
    return sorted((json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
                   for r in section.get("rows", [])))


def comparison(before, after):
    """Return real section changes; distinguish command failures from no change."""
    changes = {}
    for name in SECTIONS:
        a = before.get("sections", {}).get(name, {})
        b = after.get("sections", {}).get(name, {})
        if not a.get("ok") or not b.get("ok"):
            changes[name] = {"status": "non confrontabile", "before_ok": bool(a.get("ok")),
                             "after_ok": bool(b.get("ok"))}
        else:
            aa, bb = set(_stable_rows(a)), set(_stable_rows(b))
            if aa != bb:
                changes[name] = {
                    "status": "modificato",
                    "removed": [json.loads(x) for x in sorted(aa - bb)][:80],
                    "added": [json.loads(x) for x in sorted(bb - aa)][:80],
                }
    return changes


def report(data=None):
    """Complete local evidence for manual GitHub review; never auto-upload."""
    data = read() if data is None else data
    snapshots = data.get("snapshots", {})
    lines = ["## Diagnostica comparativa VPN / WinNAT — Issue #76",
             "Operazioni di raccolta: sola lettura. Nessuna configurazione modificata.",
             "Contesto segnalato: WinNAT-UI 1.16.0, Windows 10.0.19045, Malwarebytes 5.7.2 x64, WAN Wi-Fi.",
             "I dati di rete possono includere indirizzi IP, nomi e gateway: verificare prima di pubblicare.",
             ""]
    for phase in PHASES:
        snap = snapshots.get(phase)
        if snap:
            errors = [n for n, row in snap.get("sections", {}).items() if not row.get("ok")]
            lines.append("- " + PHASE_LABELS[phase] + ": " + snap["collected_at"]
                         + (" (sezioni non disponibili: " + ", ".join(errors) + ")" if errors else ""))
        else:
            lines.append("- " + PHASE_LABELS[phase] + ": DA ACQUISIRE")
    for a, b in (("before", "winnat"), ("winnat", "rollback"), ("before", "rollback")):
        if a in snapshots and b in snapshots:
            changes = comparison(snapshots[a], snapshots[b])
            lines.extend(["", "### " + a + " → " + b, "~~~json",
                          json.dumps(changes, indent=2, ensure_ascii=False), "~~~"])
    lines.extend(["", "### Snapshot completi (revisione manuale prima della pubblicazione)",
                  "~~~json", json.dumps(snapshots, indent=2, ensure_ascii=False), "~~~"])
    return "\n".join(lines)


def export(path, data=None):
    """Write complete snapshots and comparisons to a user-selected local UTF-8 file."""
    content = report(read() if data is None else data)
    Path(path).write_text(content, encoding="utf-8")
    return path
