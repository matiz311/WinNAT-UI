"""On-demand, generic, read-only Windows/WinNAT diagnostics for GitHub reports.

Nothing runs without a user action. Captures stay local until reviewed and submitted.
Previous samples are retained to compare changes; no assumptions about a VPN.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import network, bug_report

SECTIONS = ("adapters", "interfaces", "addresses", "routes", "nats",
            "dns", "globalRouter", "services")
MAX_OUTPUT = 512_000
MAX_SNAPSHOTS = 6
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
$r.services = Grab {
    Get-Service -ErrorAction Stop |
        Where-Object { $_.Name -match 'WinNat|SharedAccess|VPN' -or $_.DisplayName -match 'WinNAT|VPN' } |
        Select-Object Name, DisplayName, Status, StartType
}
$r | ConvertTo-Json -Depth 8 -Compress
"""




def storage_path():
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(root) / "WinNAT-UI" / "diagnostics.json"


def read(path=None):
    target = Path(path) if path is not None else storage_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema": 1, "snapshots": []}
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("snapshots"), list):
        raise ValueError("Archivio diagnostico non valido. Conservare il file prima di reimpostare.")
    return data


def capture(label="Acquisizione manuale", runner=None, path=None):
    """Acquire a generic inventory; per-command failures remain visible."""
    if not isinstance(label, str) or not label.strip() or len(label) > 80 or re.search(r"[\r\n\x00-\x1f]", label):
        raise ValueError("Etichetta diagnostica non valida.")
    execute = runner or network.ps
    raw = execute(PS_SCRIPT)
    if not isinstance(raw, str) or len(raw) > MAX_OUTPUT:
        raise ValueError("Output diagnostico assente o eccessivo.")
    sections = json.loads(raw)
    if not isinstance(sections, dict):
        raise ValueError("Output diagnostico non valido.")
    result = {}
    for name in SECTIONS:
        obj = sections.get(name)
        if not isinstance(obj, dict) or not isinstance(obj.get("ok"), bool):
            result[name] = {"ok": False, "rows": [], "error": "Sezione non restituita"}
            continue
        rows = obj.get("rows", [])
        if not isinstance(rows, list):
            rows = [rows] if rows is not None else []
        result[name] = {"ok": obj["ok"], "rows": rows}
        if not obj["ok"]:
            result[name]["error"] = str(obj.get("error", "Comando non riuscito"))[:500]
    snap = {"id": uuid4().hex, "collected_at": datetime.now(timezone.utc).isoformat(),
            "label": label.strip(), "sections": result}
    store = read(path)
    store["snapshots"] = (store["snapshots"] + [snap])[-MAX_SNAPSHOTS:]
    target = Path(path) if path is not None else storage_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return snap


def _rows(section):
    return set(json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
               for item in section.get("rows", []))


def comparison(before, after):
    """Compare consecutive captures; failed sections are not 'unchanged'."""
    changes = {}
    for name in SECTIONS:
        old = before.get("sections", {}).get(name, {})
        new = after.get("sections", {}).get(name, {})
        if not old.get("ok") or not new.get("ok"):
            changes[name] = {"status": "non confrontabile",
                             "before_ok": bool(old.get("ok")), "after_ok": bool(new.get("ok"))}
            continue
        removed, added = _rows(old) - _rows(new), _rows(new) - _rows(old)
        if removed or added:
            changes[name] = {"status": "modificato",
                             "removed": [json.loads(x) for x in sorted(removed)][:80],
                             "added": [json.loads(x) for x in sorted(added)][:80]}
    return changes


def build_report(title, description, category, data=None, version="0.0.0"):
    """Generate an editable, bounded draft for user review, not an auto-upload."""
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Inserire un titolo per la segnalazione.")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Descrivere il problema o l'aggiornamento.")
    store = read() if data is None else data
    snapshots = store.get("snapshots", [])
    parts = ["## Segnalazione diagnostica WinNAT-UI",
             "", "**Titolo:** " + title.strip(),
             "**Tipo:** " + category,
             "**Versione WinNAT-UI:** " + version,
             "**Ora UTC:** " + datetime.now(timezone.utc).isoformat(),
             "", "### Descrizione e comportamento atteso", description.strip(),
             "", "### Acquisizioni locali",
             "Snapshot disponibili: " + str(len(snapshots)),
             "Le informazioni sono raccolte in sola lettura."]
    if snapshots:
        last = snapshots[-1]
        parts.extend(["", "### Ultimo snapshot: " + last["label"] + " (" + last["collected_at"] + ")",
                      "```json", json.dumps(last["sections"], ensure_ascii=False, indent=2), "```"])
        if len(snapshots) >= 2:
            previous = snapshots[-2]
            parts.extend(["", "### Differenze rispetto al precedente: " + previous["label"],
                          "```json", json.dumps(comparison(previous, last), ensure_ascii=False, indent=2),
                          "```"])
    parts.extend(["", "### Pubblicazione",
                  "I dati possono contenere indirizzi IP, DNS, nomi di schede e dettagli di rete.",
                  "Controllare il testo prima di pubblicarlo su una Issue GitHub pubblica."])
    full = bug_report.redact("\n".join(parts))
    return bug_report._limit(full, 23800)
