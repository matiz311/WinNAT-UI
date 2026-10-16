"""Safe, explicitly scoped management of secondary IPv4 addresses on the selected LAN.

A secondary is an address with SkipAsSource=True. This intentionally does not
manage primary/DHCP addresses, routes, gateways, forwarding or WinNAT objects.
"""
import ipaddress

from . import network


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def skip_as_source(value):
    return value is True or str(value).lower() in ("true", "1")


def lan_rows(inventory, alias):
    return sorted(
        [row for row in inventory.get("ips", []) if row.get("InterfaceAlias") == alias
         and not str(row.get("IPAddress", "")).startswith("169.254.")],
        key=lambda row: (not skip_as_source(row.get("SkipAsSource")),
                         int(ipaddress.IPv4Address(row["IPAddress"])))
    )


def _address(value, prefix):
    try:
        ip = ipaddress.IPv4Address(str(value).strip())
        bits = int(prefix)
        if not 1 <= bits <= 32:
            raise ValueError
        subnet = ipaddress.IPv4Network((ip, bits), strict=False)
    except (ValueError, ipaddress.AddressValueError, TypeError) as exc:
        raise ValueError("Indirizzo IPv4 / prefisso non validi (es. 10.10.20.1/24).") from exc
    if (ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or (bits < 31 and ip in (subnet.network_address, subnet.broadcast_address))):
        raise ValueError("Usa un indirizzo IPv4 unicast assegnabile a un host.")
    return str(ip), bits


def plan(action, alias, address, prefix, inventory, old_address=None, old_prefix=None, expected_index=None):
    """Validate a user-requested edit against a fresh Windows inventory.

    Returns a normalized plan and never touches Windows. An existing address
    is editable/removable only when Windows reports SkipAsSource=True.
    """
    if action not in ("add", "edit", "remove"):
        raise ValueError("Operazione IPv4 secondario non riconosciuta.")
    network.validate_alias(alias, inventory)
    adapters = [a for a in inventory.get("adapters", []) if a.get("Name") == alias]
    if len(adapters) != 1:
        raise ValueError("Interfaccia LAN non identificabile univocamente.")
    index = int(adapters[0]["InterfaceIndex"])
    if expected_index is not None and index != int(expected_index):
        raise ValueError("L'indice della scheda LAN è cambiato: aggiorna prima di procedere.")
    iface = [i for i in inventory.get("interfaces", [])
             if i.get("InterfaceAlias") == alias and int(i.get("InterfaceIndex", -1)) == index]
    if len(iface) != 1:
        raise ValueError("Impossibile verificare lo stato IPv4 della LAN.")
    if str(iface[0].get("Dhcp", "")).lower() not in ("disabled", "false", "0"):
        raise ValueError("La LAN utilizza DHCP: configurala staticamente prima di aggiungere IPv4 secondari.")
    primary = [row for row in lan_rows(inventory, alias)
               if not skip_as_source(row.get("SkipAsSource"))]
    if not primary:
        raise ValueError("Manca un IPv4 principale sulla LAN: configura prima l'indirizzo primario.")
    ip, bits = _address(address, prefix)
    old_ip, old_bits = (None, None)
    if action == "edit":
        old_ip, old_bits = _address(old_address, old_prefix)
        if (old_ip, old_bits) == (ip, bits):
            raise ValueError("Non ci sono modifiche da applicare.")
    elif action == "remove":
        old_ip, old_bits = ip, bits
    all_ips = inventory.get("ips", [])
    current_old = [row for row in all_ips if row.get("InterfaceAlias") == alias
                   and row.get("IPAddress") == old_ip] if old_ip else []
    if old_ip:
        if len(current_old) != 1 or int(current_old[0].get("PrefixLength", -1)) != old_bits:
            raise ValueError("L'IPv4 secondario da modificare non è più presente con il prefisso atteso.")
        if not skip_as_source(current_old[0].get("SkipAsSource")):
            raise ValueError("Indirizzo principale/non secondario: modifica o eliminazione bloccata.")
        if str(current_old[0].get("PrefixOrigin", "Manual")).lower() == "dhcp":
            raise ValueError("Indirizzo DHCP: modifica o eliminazione bloccata.")
    collisions = [row for row in all_ips if row.get("IPAddress") == ip
                  and not (old_ip == ip and row.get("InterfaceAlias") == alias
                           and int(row.get("PrefixLength", -1)) == old_bits)]
    if collisions:
        raise ValueError("Indirizzo IPv4 già presente: non sovrascrivo gli IP esistenti.")
    if action in ("add", "edit"):
        subnet = ipaddress.IPv4Network((ip, bits), strict=False)
        for row in all_ips:
            if row.get("InterfaceAlias") in (alias, None):
                continue
            try:
                other = ipaddress.IPv4Network(
                    (row["IPAddress"], int(row["PrefixLength"])), strict=False)
            except (KeyError, ValueError):
                continue
            if subnet.overlaps(other):
                raise ValueError("La nuova subnet si sovrappone a " + str(row["InterfaceAlias"])
                                 + " (" + str(other) + ").")
    return {"action": action, "alias": alias, "index": index, "ip": ip, "prefix": bits,
            "old_ip": old_ip, "old_prefix": old_bits}


def script_for(candidate):
    """Live Windows guards are repeated immediately before any write."""
    p = candidate
    base = [
        "$ErrorActionPreference='Stop'",
        "$alias=" + quote(p["alias"]),
        "$index=" + str(p["index"]),
        "$ip=" + quote(p["ip"]),
        "$prefix=" + str(p["prefix"]),
        "$adapter=Get-NetAdapter -Name $alias -ErrorAction Stop",
        "if([int]$adapter.InterfaceIndex -ne $index){throw 'Interfaccia LAN cambiata'}",
        "$iface=Get-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -ErrorAction Stop",
        "if($iface.Dhcp -ne 'Disabled'){throw 'DHCP LAN abilitato'}",
        "$all=@(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -ErrorAction Stop)",
        "if(@($all | Where-Object { -not $_.SkipAsSource -and $_.IPAddress -notlike '169.254.*' }).Count -lt 1)"
        "{throw 'IPv4 principale LAN assente'}",
    ]
    if p["action"] in ("edit", "remove"):
        base += [
            "$oldIp=" + quote(p["old_ip"]),
            "$oldPrefix=" + str(p["old_prefix"]),
            "$old=@($all | Where-Object { $_.IPAddress -eq $oldIp -and $_.PrefixLength -eq $oldPrefix -and $_.SkipAsSource })",
            "if($old.Count -ne 1){throw 'IPv4 secondario originario cambiato o non gestibile'}",
        ]
    if p["action"] in ("add", "edit"):
        base += [
            "$collisions=@(Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ip -ErrorAction SilentlyContinue)",
            "if(@($collisions | Where-Object { $_.InterfaceIndex -ne $index -or $_.IPAddress -ne $oldIp"
            " -or $_.PrefixLength -ne $oldPrefix }).Count -gt 0){throw 'Conflitto IPv4 sul sistema'}"
            if p["action"] == "edit" else
            "if($collisions.Count -gt 0){throw 'Conflitto IPv4 sul sistema'}",
        ]
        if p["action"] == "edit" and p["old_ip"] == p["ip"]:
            base.append("$old[0] | Set-NetIPAddress -PrefixLength $prefix -SkipAsSource $true -ErrorAction Stop")
        else:
            base.append("New-NetIPAddress -InterfaceIndex $index -IPAddress $ip -PrefixLength $prefix"
                        " -SkipAsSource $true -ErrorAction Stop | Out-Null")
            if p["action"] == "edit":
                base.append("$old[0] | Remove-NetIPAddress -Confirm:$false -ErrorAction Stop")
    else:
        base.append("$old[0] | Remove-NetIPAddress -Confirm:$false -ErrorAction Stop")
    return "\n".join(base) + "\n"


def apply(candidate):
    network.ps(script_for(candidate))


def verify(candidate, inventory):
    p = candidate
    matching = [row for row in inventory.get("ips", [])
                if row.get("InterfaceAlias") == p["alias"]]
    new = [row for row in matching if row.get("IPAddress") == p["ip"]
           and int(row.get("PrefixLength", -1)) == p["prefix"]
           and skip_as_source(row.get("SkipAsSource"))]
    old = [row for row in matching if row.get("IPAddress") == p["old_ip"]
           and int(row.get("PrefixLength", -1)) == p["old_prefix"]]
    valid = (len(new) == 0 if p["action"] == "remove" else len(new) == 1)
    if p["action"] == "edit":
        valid = valid and not old
    if not valid:
        raise RuntimeError("Verifica IPv4 secondario non riuscita dopo il comando PowerShell.")
