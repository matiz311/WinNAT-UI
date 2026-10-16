"""Windows network operations. Requires Windows PowerShell 5.1 and administrator for mutations."""
import ctypes
import contextvars
import ipaddress
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

POWERSHELL = "powershell.exe"

# Set in the Commit worker only; regular inventory refreshes never spam the UI.
command_logger = contextvars.ContextVar("command_logger", default=None)


def _emit_command_event(kind, value):
    callback = command_logger.get()
    if callback is not None:
        try:
            callback(kind, str(value))
        except Exception:
            pass  # A UI-log failure must never affect network mutations.


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
    _emit_command_event("command", script)
    process = subprocess.run(
        # Force UTF-8 output: otherwise Windows uses the OEM code page (e.g. 850 on
        # Italian systems) and accented adapter names or messages are garbled.
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command",
         # Same line as the script's first line, so "In riga:X" still matches the numbering below.
         "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; " + script],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60, shell=False,
        startupinfo=startup)
    if process.stdout:
        _emit_command_event("stdout", process.stdout.lstrip("\ufeff"))
    if process.stderr:
        _emit_command_event("stderr", process.stderr)
    _emit_command_event("status", "PowerShell terminato con codice " + str(process.returncode))
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
    return process.stdout.lstrip("\ufeff").strip()

def collect():
    """Collect independent configuration groups concurrently. Sessions are separate."""
    scripts = {
        "adapters": "Get-NetAdapter | Select-Object Name,InterfaceIndex,InterfaceDescription,Status,LinkSpeed",
        "ips": "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,IPAddress,PrefixLength,AddressState,SkipAsSource,PrefixOrigin",
        "routes": "Get-NetRoute -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,DestinationPrefix,NextHop,RouteMetric,InterfaceMetric",
        "interfaces": "Get-NetIPInterface -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,Forwarding,Dhcp,AutomaticMetric,ConnectionState,InterfaceMetric",
        "nats": "Get-NetNat | Select-Object Name,InternalIPInterfaceAddressPrefix,ExternalIPInterfaceAddressPrefix,Active",
        "natMappings": "Get-NetNatStaticMapping | Select-Object NatName,Protocol,ExternalIPAddress,ExternalPort,InternalIPAddress,InternalPort",
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


def save_commit_state(stage, data, context=None):
    """Persist a local diagnostic checkpoint for candidate/pre/post commit state."""
    safe_stage = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(stage)).strip("-") or "state"
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WinNAT-UI" / "commit-states"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    path = folder / (stamp.strftime("%Y%m%d-%H%M%S-%f") + "-" + safe_stage + ".json")
    payload = {
        "stage": str(stage),
        "captured_at": stamp.isoformat(),
        "inventory": data,
    }
    if context is not None:
        payload["context"] = context
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
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

def shared_nat_prefix(existing_prefix, requested_prefix):
    """Smallest CIDR containing both subnet ranges; IPs themselves are unchanged."""
    first = ipaddress.IPv4Network(existing_prefix)
    second = ipaddress.IPv4Network(requested_prefix)
    low = min(int(first.network_address), int(second.network_address))
    high = max(int(first.broadcast_address), int(second.broadcast_address))
    length = 32 - (low ^ high).bit_length()
    return str(ipaddress.IPv4Network((low, length), strict=False))


def nat_add_preflight(name, prefix, data):
    """Idempotent check for Add NAT, not a network topology validator.

    Unrelated NAT objects do not block creation. No change to any existing NAT
    object is ever made by this action.
    """
    name = validate_name(name)
    prefix = validate_prefix(prefix)
    matches = [n for n in data.get("nats", []) if n.get("Name") == name]
    if not matches:
        return "create"
    if len(matches) == 1 and (
        matches[0].get("InternalIPInterfaceAddressPrefix") == prefix
        and not matches[0].get("ExternalIPInterfaceAddressPrefix")
    ):
        return "already-present"
    raise ValueError(
        "Esiste già un NAT con nome '" + name +
        "' e configurazione differente. Scegli un nome diverso oppure modifica "
        "esplicitamente la regola esistente."
    )



def nat_network_preflight(name, prefix, data):
    """Gateway profile compatibility, separate from direct Add NAT semantics."""
    validate_name(name)
    prefix = validate_prefix(prefix)
    nats = data.get("nats", [])
    if len(nats) > 1:
        raise ValueError("Più WinNAT rilevati: la migrazione automatica del gateway non è applicabile.")
    if not nats:
        return "create"
    try:
        internal = ipaddress.IPv4Network(nats[0]["InternalIPInterfaceAddressPrefix"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("Prefisso WinNAT esistente non verificabile.")
    if ipaddress.IPv4Network(prefix).subnet_of(internal):
        return "already-covered"
    return "expand"



def nat_expansion_script(requested_prefix, inventory, allow_restore=False):
    """Return guarded PowerShell for expanding one physical NAT with rollback.

    Preserves its name, external prefix, TCP/UDP mappings and common tunables.
    Rebuilding a WinNAT interrupts existing NAT sessions. Never touch LAN/WAN IPs.
    """
    requested_prefix = validate_prefix(requested_prefix)
    action = nat_network_preflight("WinNAT-UI", requested_prefix, inventory)
    if action != "expand" and not (allow_restore and action == "already-covered"):
        raise ValueError("Espansione WinNAT non necessaria.")
    previous = inventory["nats"][0]
    name = str(previous["Name"])
    if not name:
        raise ValueError("Nome WinNAT esistente mancante.")
    old_prefix = validate_prefix(previous["InternalIPInterfaceAddressPrefix"])
    new_prefix = requested_prefix if allow_restore else shared_nat_prefix(old_prefix, requested_prefix)
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = r"""
$ErrorActionPreference = 'Stop'
$name = __NAME__
$oldPrefix = __OLD__
$newPrefix = __NEW__
$oldObjects = @(Get-NetNat -ErrorAction Stop)
if($oldObjects.Count -ne 1 -or $oldObjects[0].Name -ne $name -or
   $oldObjects[0].InternalIPInterfaceAddressPrefix -ne $oldPrefix) {
  throw 'WinNAT modificato dopo lo snapshot: nessuna migrazione eseguita'
}
$old = $oldObjects[0]
$oldMappings = @(Get-NetNatStaticMapping -NatName $name -ErrorAction Stop)
$oldExternalAddresses = @(Get-NetNatExternalAddress -NatName $name -ErrorAction Stop)
if($oldExternalAddresses.Count -gt 0) {
  throw 'WinNAT ha external addresses dedicate: migrazione automatica non sicura; nessuna modifica'
}
foreach($entry in $oldMappings) {
  if($entry.Protocol.ToString() -notin @('TCP','UDP','6','17')) {
    throw 'Mapping NAT con protocollo non ripristinabile: nessuna modifica'
  }
}
function Make-Nat([string]$prefix) {
  $args = @{Name=$name;InternalIPInterfaceAddressPrefix=$prefix;ErrorAction='Stop'}
  if($old.ExternalIPInterfaceAddressPrefix) {
    $args.ExternalIPInterfaceAddressPrefix = $old.ExternalIPInterfaceAddressPrefix
  }
  if($old.InternalRoutingDomainId) {
    $args.InternalRoutingDomainId = $old.InternalRoutingDomainId
  }
  New-NetNat @args | Out-Null
  $options = @{}
  $setParameters = (Get-Command Set-NetNat -ErrorAction Stop).Parameters
  foreach($key in @('TcpEstablishedConnectionTimeout','TcpTransientConnectionTimeout',
                   'UdpIdleSessionTimeout','IcmpQueryTimeout','TcpFilteringBehavior',
                   'UdpFilteringBehavior','UdpInboundRefresh')) {
    if($setParameters.ContainsKey($key) -and $old.PSObject.Properties[$key] -and
       $null -ne $old.$key) { $options[$key] = $old.$key }
  }
  if($options.Count -gt 0) { Set-NetNat -Name $name @options -ErrorAction Stop | Out-Null }
}
function Restore-Mappings {
  foreach($entry in $oldMappings) {
    $protocol = if($entry.Protocol.ToString() -in @('6','TCP')) {'TCP'} else {'UDP'}
    $args = @{NatName=$name;Protocol=$protocol;ExternalIPAddress=$entry.ExternalIPAddress;
              ExternalPort=[int]$entry.ExternalPort;InternalIPAddress=$entry.InternalIPAddress;
              InternalPort=[int]$entry.InternalPort;ErrorAction='Stop'}
    if($entry.RemoteExternalIPAddressPrefix) {
      $args.RemoteExternalIPAddressPrefix = $entry.RemoteExternalIPAddressPrefix
    }
    if($entry.InternalRoutingDomainId) {
      $args.InternalRoutingDomainId = $entry.InternalRoutingDomainId
    }
    Add-NetNatStaticMapping @args | Out-Null
  }
}
function Verify-State([string]$expectedPrefix) {
  $nats = @(Get-NetNat -ErrorAction Stop)
  if($nats.Count -ne 1 -or $nats[0].Name -ne $name -or
     $nats[0].InternalIPInterfaceAddressPrefix -ne $expectedPrefix) {
    throw 'WinNAT non corrisponde al prefisso richiesto'
  }
  $present = @(Get-NetNatStaticMapping -NatName $name -ErrorAction Stop)
  if($present.Count -ne $oldMappings.Count) {
    throw 'Il numero di mapping statici non coincide dopo la migrazione'
  }
  foreach($entry in $oldMappings) {
    $same = @($present | Where-Object {
      ($_.Protocol.ToString() -eq $entry.Protocol.ToString() -or
       ($_.Protocol.ToString() -in @('6','TCP') -and $entry.Protocol.ToString() -in @('6','TCP')) -or
       ($_.Protocol.ToString() -in @('17','UDP') -and $entry.Protocol.ToString() -in @('17','UDP'))) -and
      $_.ExternalIPAddress -eq $entry.ExternalIPAddress -and
      $_.ExternalPort -eq $entry.ExternalPort -and
      $_.InternalIPAddress -eq $entry.InternalIPAddress -and
      $_.InternalPort -eq $entry.InternalPort
    })
    if($same.Count -ne 1) { throw 'Mapping statico originale non ripristinato correttamente' }
  }
}
$removed = $false
try {
  Remove-NetNat -Name $name -Confirm:$false -ErrorAction Stop
  $removed = $true
  Make-Nat $newPrefix
  Restore-Mappings
  Verify-State $newPrefix
} catch {
  $cause = $_
  if(-not $removed) { throw $cause }
  try {
    $replacement = @(Get-NetNat -Name $name -ErrorAction SilentlyContinue)
    if($replacement.Count -gt 0) { Remove-NetNat -Name $name -Confirm:$false -ErrorAction Stop }
    Make-Nat $oldPrefix
    Restore-Mappings
    Verify-State $oldPrefix
  } catch {
    throw ('Espansione WinNAT fallita; RIPRISTINO INCOMPLETO: ' +
           $cause.Exception.Message + '; ripristino: ' + $_.Exception.Message)
  }
  throw ('Espansione WinNAT fallita; configurazione originale ripristinata: ' +
         $cause.Exception.Message)
}
"""
    return (script.replace("__NAME__", quote(name))
                  .replace("__OLD__", quote(old_prefix))
                  .replace("__NEW__", quote(new_prefix)))


def expand_nat(requested_prefix, inventory):
    """Apply an explicit, reversible rebuild of the existing physical WinNAT."""
    script = nat_expansion_script(requested_prefix, inventory)
    ps(script)
    state = collect()
    if len(state.get("nats", [])) != 1:
        raise RuntimeError("Verifica WinNAT dopo espansione fallita: istanze inattese.")
    expected = shared_nat_prefix(inventory["nats"][0]["InternalIPInterfaceAddressPrefix"],
                                 requested_prefix)
    if state["nats"][0].get("InternalIPInterfaceAddressPrefix") != expected:
        raise RuntimeError("Verifica WinNAT dopo espansione fallita: prefisso diverso.")
    return state



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
    if nat_network_preflight("WinNAT-UI", prefix, data) == "expand":
        data = expand_nat(prefix, data)
    # Existing primary/secondary addresses, gateways and routes remain untouched.
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
$existingNat = @(Get-NetNat -ErrorAction Stop)
if($existingNat.Count -gt 1) { throw 'Istanze WinNAT multiple rilevate' }
if($existingNat.Count -eq 0) { New-NetNat -Name 'WinNAT-UI' -InternalIPInterfaceAddressPrefix '%s' -ErrorAction Stop | Out-Null }
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
