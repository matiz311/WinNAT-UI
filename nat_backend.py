"""Headless backend for static WinNAT mappings and secondary IPv4 addresses.

The application may manage multiple independent WinNAT objects. Mapping operations
target one explicitly named NAT and never mutate unrelated NAT objects.
"""
import ipaddress
import network


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _nat(inventory, name):
    matching = [n for n in inventory.get("nats", []) if n.get("Name") == name]
    if len(matching) != 1:
        raise ValueError("Serve un WinNAT esistente univoco per creare mapping; non creo NAT concorrenti.")
    return matching[0]


def ensure_secondary_ipv4(interface_alias, address, prefix_length, inventory, skip_as_source=True):
    """Add one secondary IPv4 without replacing primary addresses or default routes.

    Does not disable DHCP implicitly. Returns True when a command ran.
    """
    address = str(ipaddress.IPv4Address(address))
    prefix_length = int(prefix_length)
    subnet = ipaddress.IPv4Network((address, prefix_length), strict=False)
    if not (1 <= prefix_length <= 32) or address in (str(subnet.network_address), str(subnet.broadcast_address)):
        raise ValueError("Indirizzo IPv4 secondario o maschera non validi.")
    network.validate_alias(interface_alias, inventory)
    matches = [ip for ip in inventory.get("ips", []) if ip.get("IPAddress") == address]
    if any(ip.get("InterfaceAlias") != interface_alias or int(ip.get("PrefixLength", -1)) != prefix_length
           for ip in matches):
        raise ValueError("Indirizzo IPv4 già assegnato a interfaccia o prefisso differente.")
    if matches:
        return False
    interfaces = [i for i in inventory.get("interfaces", [])
                  if i.get("InterfaceAlias") == interface_alias]
    if len(interfaces) != 1:
        raise ValueError("Stato interfaccia non verificabile.")
    if str(interfaces[0].get("Dhcp", "")).lower() not in ("disabled", "false", "0"):
        raise ValueError("Interfaccia con DHCP abilitato: non aggiungo IP statici per evitare disabilitazione implicita.")
    script = (
        "$ErrorActionPreference='Stop'\n"
        "$alias=" + _quote(interface_alias) + "\n"
        "$ip=" + _quote(address) + "\n"
        "$prefix=" + str(prefix_length) + "\n"
        "$existing=@(Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ip -ErrorAction SilentlyContinue)\n"
        "if(@($existing | Where-Object { $_.InterfaceAlias -ne $alias -or $_.PrefixLength -ne $prefix }).Count -gt 0)"
        "{ throw 'Indirizzo IPv4 in conflitto' }\n"
        "if($existing.Count -eq 0){\n"
        "  $iface=Get-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction Stop\n"
        "  if($iface.Dhcp -ne 'Disabled'){ throw 'DHCP attivo' }\n"
        "  New-NetIPAddress -InterfaceAlias $alias -IPAddress $ip -PrefixLength $prefix"
        " -SkipAsSource $" + ("true" if skip_as_source else "false") + " -ErrorAction Stop | Out-Null\n"
        "}\n"
    )
    network.ps(script)
    return True


def ensure_nat_mapping(nat_name, protocol, external_port, internal_address, internal_port, inventory,
                       external_address="0.0.0.0"):
    """Create a static mapping on one explicitly named existing WinNAT."""
    network.validate_name(nat_name)
    nat = _nat(inventory, nat_name)
    protocol = str(protocol).upper()
    if protocol not in ("TCP", "UDP"):
        raise ValueError("Protocollo ammesso: TCP o UDP.")
    external_port = int(external_port)
    internal_port = int(internal_port)
    if not (1 <= external_port <= 65535 and 1 <= internal_port <= 65535):
        raise ValueError("Porta TCP/UDP fuori intervallo.")
    external_address = str(ipaddress.IPv4Address(external_address))
    internal_address = str(ipaddress.IPv4Address(internal_address))
    subnet = ipaddress.IPv4Network(nat["InternalIPInterfaceAddressPrefix"], strict=False)
    if ipaddress.IPv4Address(internal_address) not in subnet:
        raise ValueError("Indirizzo interno fuori dal prefisso del WinNAT esistente.")
    mappings = inventory.get("natMappings")
    if mappings is None:
        raise ValueError("Inventario mapping NAT non disponibile: aggiorna lo snapshot.")
    matching = [m for m in mappings if str(m.get("NatName")) == nat_name
                and str(m.get("Protocol", "")).upper() in (protocol, "6" if protocol == "TCP" else "17")
                and int(m.get("ExternalPort", -1)) == external_port
                and str(m.get("ExternalIPAddress")) == external_address]
    if matching:
        if len(matching) == 1 and str(matching[0].get("InternalIPAddress")) == internal_address and int(
                matching[0].get("InternalPort", -1)) == internal_port:
            return False
        raise ValueError("Mapping esterno già occupato con destinazione differente.")
    # Revalidate against live Windows state to prevent stale-inventory duplication.
    script = (
        "$ErrorActionPreference='Stop'\n"
        "$name=" + _quote(nat_name) + "\n"
        "$protocol=" + _quote(protocol) + "\n"
        "$external=" + _quote(external_address) + "\n"
        "$port=" + str(external_port) + "\n"
        "$internal=" + _quote(internal_address) + "\n"
        "$internalPort=" + str(internal_port) + "\n"
        "$nat=Get-NetNat -Name $name -ErrorAction Stop\n"
        "if($nat.InternalIPInterfaceAddressPrefix -ne " + _quote(str(subnet)) + "){ throw 'Prefisso WinNAT modificato' }\n"
        "$existing=@(Get-NetNatStaticMapping -NatName $name -ErrorAction Stop | Where-Object { "
        "($_.Protocol.ToString() -eq $protocol -or $_.Protocol.ToString() -eq $(if($protocol -eq 'TCP'){'6'}else{'17'})) -and $_.ExternalIPAddress -eq $external -and $_.ExternalPort -eq $port })\n"
        "if($existing.Count -gt 0){\n"
        "  if(@($existing | Where-Object { $_.InternalIPAddress -ne $internal -or "
        "$_.InternalPort -ne $internalPort }).Count -gt 0){ throw 'Mapping WinNAT in conflitto' }\n"
        "}else{ Add-NetNatStaticMapping -NatName $name -Protocol $protocol -ExternalIPAddress $external"
        " -ExternalPort $port -InternalIPAddress $internal -InternalPort $internalPort -ErrorAction Stop | Out-Null }\n"
    )
    network.ps(script)
    return True
