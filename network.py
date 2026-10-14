"""Windows network operations. Requires Windows PowerShell 5.1 and administrator for mutations."""
import ctypes
import ipaddress
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

POWERSHELL = "powershell.exe"

def admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ps(script):
    """Execute readable PowerShell commands, without Base64, packing or shell invocation."""
    startup = subprocess.STARTUPINFO() if os.name == "nt" else None
    if startup is not None:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
    process = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=60, shell=False, startupinfo=startup)
    if process.returncode:
        # Diagnostic only: preserve all output and the exact executed script.
        # Line numbers allow matching "In riga:X" in localized PowerShell errors.
        numbered_script = "\n".join(
            f"{number:04d} | {line}" for number, line in enumerate(script.splitlines(), 1))
        parts = [
            "ESECUZIONE POWERSHELL NON RIUSCITA",
            "Exit code: " + str(process.returncode),
            "Interprete: " + POWERSHELL + " -NoProfile -NonInteractive -Command",
            "Timeout configurato: 60 secondi",
            "STDERR (integrale):\n" + (process.stderr if process.stderr else "(vuoto)"),
            "STDOUT (integrale):\n" + (process.stdout if process.stdout else "(vuoto)"),
            "SCRIPT ESEGUITO (righe numerate):\n" + numbered_script,
            "Nota: lo script contiene configurazioni IP/NAT. Controllare i dati prima di condividerlo."
        ]
        raise RuntimeError("\n\n".join(parts))
    return process.stdout.strip()

def collect():
    """Collect independent configuration groups concurrently. Sessions are separate."""
    scripts = {
        "adapters": "Get-NetAdapter | Select-Object Name,InterfaceIndex,InterfaceDescription,Status,LinkSpeed",
        "ips": "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,IPAddress,PrefixLength,AddressState",
        "routes": "Get-NetRoute -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,DestinationPrefix,NextHop,RouteMetric,InterfaceMetric",
        "interfaces": "Get-NetIPInterface -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,Forwarding,Dhcp,AutomaticMetric,ConnectionState,InterfaceMetric",
        "nats": "Get-NetNat | Select-Object Name,InternalIPInterfaceAddressPrefix,ExternalIPInterfaceAddressPrefix,Active",
        "ics": "Get-Service SharedAccess | Select-Object Name,Status,StartType",
        "dns": "Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,ServerAddresses",
        "globalRouter": "(Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters' -Name IPEnableRouter -ErrorAction SilentlyContinue).IPEnableRouter"
    }
    def run_group(item):
        key, expression = item
        command = "$ErrorActionPreference='Stop'; @(" + expression + ") | ConvertTo-Json -Compress -Depth 6"
        raw = ps(command)
        value = json.loads(raw) if raw else []
        return key, value if isinstance(value, list) else ([] if value is None else [value])
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = dict(pool.map(run_group, scripts.items()))
    result["ics"] = result["ics"][0] if result["ics"] else {}
    result["globalRouter"] = int(result["globalRouter"][0] or 0) if result["globalRouter"] else 0
    # ICS COM discovery is separated so COM errors don't hide the other results.
    try:
        raw = ps(r"""
$ErrorActionPreference='Stop'
$manager=New-Object -ComObject HNetCfg.HNetShare
@(
foreach($connection in $manager.EnumEveryConnection()){
  $props=$manager.NetConnectionProps($connection)
  $config=$manager.INetSharingConfigurationForINetConnection($connection)
  [pscustomobject]@{Name=$props.Name;SharingEnabled=[bool]$config.SharingEnabled;SharingConnectionType=$(if($config.SharingEnabled){[int]$config.SharingConnectionType}else{$null})}
}
) | ConvertTo-Json -Compress -Depth 5
""")
        value = json.loads(raw) if raw else []
        result["icsConnections"] = value if isinstance(value, list) else ([] if value is None else [value])
    except Exception as exc:
        result["icsConnections"] = [{"Name": "ICS inspection error", "Error": str(exc)}]
    return result

def sessions():
    """Load active NAT sessions on demand, independently of interface discovery."""
    script = r"""
$ErrorActionPreference = 'Stop'
@(Get-NetNatSession | Select-Object -First 500 NatName,InternalSourceAddress,InternalSourcePort,InternalDestinationAddress,InternalDestinationPort,ExternalSourceAddress,ExternalSourcePort,ExternalDestinationAddress,ExternalDestinationPort,Protocol) | ConvertTo-Json -Depth 4 -Compress
"""
    raw = ps(script)
    if not raw:
        return []
    value = json.loads(raw)
    return value if isinstance(value, list) else [value]


def snapshot(data):
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinNAT-UI" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("network-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)

def validate_name(name):
    if not name or len(name) > 64 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in name):
        raise ValueError("Nome NAT non valido (solo lettere, numeri, - e _).")
    return name

def validate_alias(alias, data):
    names = [a["Name"] for a in data.get("adapters", [])]
    if alias not in names:
        raise ValueError("Interfaccia non presente nell'inventario.")
    return alias.replace("'", "''")

def validate_prefix(prefix):
    network = ipaddress.IPv4Network(prefix, strict=True)
    if not network.is_private:
        # Public ranges can be legitimate in laboratories; don't silently rewrite them.
        pass
    if network.prefixlen < 8 or network.prefixlen > 30:
        raise ValueError("Prefisso IPv4 supportato in questa procedura: /8 - /30.")
    return str(network)

def validate_gateway(address, network):
    ip = ipaddress.IPv4Address(address)
    if ip not in network or ip in (network.network_address, network.broadcast_address):
        raise ValueError("L'IP LAN deve essere un host utilizzabile nel prefisso.")
    return str(ip)

def create_nat(name, prefix):
    validate_name(name)
    validate_prefix(prefix)
    return ps("$ErrorActionPreference='Stop'; New-NetNat -Name '%s' -InternalIPInterfaceAddressPrefix '%s' | Out-String" % (name, prefix))

def remove_nat(name):
    validate_name(name)
    return ps("$ErrorActionPreference='Stop'; Remove-NetNat -Name '%s' -Confirm:$false" % name)

def setup(lan, prefix, gateway, data):
    subnet = ipaddress.IPv4Network(validate_prefix(prefix))
    validate_gateway(gateway, subnet)
    alias = validate_alias(lan, data)
    # No implicit removal of existing addresses, gateways, NATs or ICS.
    script = """
$ErrorActionPreference='Stop'
$alias='%s'
$ip='%s'
$prefix=%d
$existing = @(Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.IPAddress -eq $ip -and $_.PrefixLength -eq $prefix})
if($existing.Count -eq 0) { New-NetIPAddress -InterfaceAlias $alias -IPAddress $ip -PrefixLength $prefix -ErrorAction Stop | Out-Null }
Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop
$routes = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -AddressFamily IPv4 -ErrorAction SilentlyContinue)
if($routes.Count -eq 0) { throw 'Nessuna route predefinita disponibile: impossibile individuare la WAN.' }
New-NetNat -Name 'WinNAT-UI' -InternalIPInterfaceAddressPrefix '%s' -ErrorAction Stop | Out-Null
'Configuration complete'
""" % (alias, gateway, subnet.prefixlen, prefix)
    result = ps(script)
    # Registra solo ciò che il wizard ha predisposto. Il teardown è conservativo.
    state = {
        "lan": lan, "prefix": prefix, "gateway": gateway,
        "nat": "WinNAT-UI",
        "added_ip": not any(ip.get("InterfaceAlias") == lan and ip.get("IPAddress") == gateway and ip.get("PrefixLength") == subnet.prefixlen for ip in data.get("ips", [])),
        "created": datetime.now().isoformat()
    }
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")
    return result

def state_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinNAT-UI" / "managed-setup.json"

def managed_state():
    path = state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def teardown(data):
    state = managed_state()
    if not state:
        raise ValueError("Non esiste un setup tracciato dall'applicazione. Rimuovi eventuali NAT manualmente.")
    name = validate_name(state["nat"])
    prefix = validate_prefix(state["prefix"])
    gateway = validate_gateway(state["gateway"], ipaddress.IPv4Network(prefix))
    alias = validate_alias(state["lan"], data)
    matching = [n for n in data.get("nats", [])
                if n.get("Name") == name and n.get("InternalIPInterfaceAddressPrefix") == prefix]
    if len(matching) != 1:
        raise ValueError("La regola NAT gestita non coincide con quella attuale. Operazione interrotta.")
    # Non rimuovere altri IP, gateway, DHCP, ICS, VPN o NAT estranei.
    remove_ip = bool(state.get('added_ip', False))
    script = """
$ErrorActionPreference='Stop'
$nat = Get-NetNat -Name '%s' -ErrorAction Stop
if($nat.InternalIPInterfaceAddressPrefix -ne '%s'){throw 'Prefisso NAT cambiato'}
Remove-NetNat -Name '%s' -Confirm:$false -ErrorAction Stop
$removeIp = $%s
$ip = Get-NetIPAddress -InterfaceAlias '%s' -AddressFamily IPv4 -IPAddress '%s' -ErrorAction SilentlyContinue |
    Where-Object {$_.PrefixLength -eq %d}
if($ip -and $removeIp){Remove-NetIPAddress -InputObject $ip -Confirm:$false -ErrorAction Stop}
'Managed NAT removed. IP forwarding has been preserved.'
""" % (name, prefix, name, 'true' if remove_ip else 'false', alias, gateway, ipaddress.IPv4Network(prefix).prefixlen)
    result = ps(script)
    state_path().unlink(missing_ok=True)
    return result

def remove_existing_configuration(lan, prefix, gateway, nat_names, data, remove_address=False):
    """Explicitly remove selected pre-existing NATs and optionally the exact LAN IP.

    Does not touch ICS, unrelated interfaces or forwarding. Backup is performed by caller.
    """
    subnet = ipaddress.IPv4Network(validate_prefix(prefix))
    validate_gateway(gateway, subnet)
    alias = validate_alias(lan, data)
    existing = {n.get("Name") for n in data.get("nats", [])}
    names = list(dict.fromkeys(validate_name(n) for n in nat_names))
    if not names or any(n not in existing for n in names):
        raise ValueError("Seleziona una o piu regole NAT esistenti.")
    names_literal = ",".join("'" + n + "'" for n in names)
    script = """
$ErrorActionPreference='Stop'
$names=@(%s)
foreach($name in $names) {
  $rule=Get-NetNat -Name $name -ErrorAction Stop
  if($null -eq $rule) { throw "Regola NAT non trovata: $name" }
}
foreach($name in $names) { Remove-NetNat -Name $name -Confirm:$false -ErrorAction Stop }
$removeAddress=$%s
if($removeAddress) {
  $addr=Get-NetIPAddress -InterfaceAlias '%s' -IPAddress '%s' -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.PrefixLength -eq %d }
  if($addr) { $addr | Remove-NetIPAddress -Confirm:$false -ErrorAction Stop }
}
'Configuration removal completed'
""" % (names_literal, 'true' if remove_address else 'false', alias, gateway, subnet.prefixlen)
    return ps(script)
