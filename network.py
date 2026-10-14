"""Windows network operations. Requires Windows PowerShell 5.1 and administrator for mutations."""
import base64
import ctypes
import ipaddress
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

POWERSHELL = "powershell.exe"

def admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ps(script):
    # EncodeCommand avoids shell quoting and injection; all input is strictly validated.
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    process = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, text=True, timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if process.returncode:
        raise RuntimeError((process.stderr or process.stdout).strip() or "PowerShell failed")
    return process.stdout.strip()

def collect():
    script = r"""
$ErrorActionPreference = 'Stop'
function Arr($x) { @($x) }
$adapters = @(Get-NetAdapter | Select-Object Name,InterfaceIndex,InterfaceDescription,Status,LinkSpeed)
$ips = @(Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,IPAddress,PrefixLength,AddressState)
$routes = @(Get-NetRoute -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,DestinationPrefix,NextHop,RouteMetric,InterfaceMetric)
$ifaces = @(Get-NetIPInterface -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,Forwarding,Dhcp,ConnectionState,InterfaceMetric)
$nats = @(Get-NetNat | Select-Object Name,InternalIPInterfaceAddressPrefix,ExternalIPInterfaceAddressPrefix,Active)
$sessions = @(Get-NetNatSession | Select-Object -First 100 NatName,InternalSourceAddress,InternalDestinationAddress,ExternalSourceAddress,ExternalDestinationAddress,Protocol)
$ics = Get-Service SharedAccess | Select-Object Name,Status,StartType
$connections = @()
try {
  $manager = New-Object -ComObject HNetCfg.HNetShare
  foreach ($connection in $manager.EnumEveryConnection()) {
    $props = $manager.NetConnectionProps($connection)
    $config = $manager.INetSharingConfigurationForINetConnection($connection)
    $connections += [pscustomobject]@{
      Name=$props.Name
      SharingEnabled=[bool]$config.SharingEnabled
      SharingConnectionType=$(if($config.SharingEnabled){[int]$config.SharingConnectionType}else{$null})
    }
  }
} catch { $connections += [pscustomobject]@{Name='ICS inspection error';Error=$_.Exception.Message} }
[pscustomobject]@{adapters=$adapters;ips=$ips;routes=$routes;interfaces=$ifaces;nats=$nats;sessions=$sessions;ics=$ics;icsConnections=$connections} | ConvertTo-Json -Depth 8 -Compress
"""
    return json.loads(ps(script))

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
""" % (name, prefix, name, alias, gateway, 'true' if remove_ip else 'false', ipaddress.IPv4Network(prefix).prefixlen)
    result = ps(script)
    state_path().unlink(missing_ok=True)
    return result
