"""Explicit Windows networking plan operations (not tied to application ownership)."""
import ipaddress
import network

def validate_interface(name, inventory):
    matches=[a for a in inventory.get("adapters",[]) if a.get("Name")==name]
    if len(matches)!=1: raise ValueError("Interfaccia non trovata: "+name)
    return name

def quote(value):
    return "'" + str(value).replace("'", "''") + "'"

def preflight(plan, inventory):
    lan=validate_interface(plan["lan"],inventory)
    wan=validate_interface(plan["wan"],inventory)
    if lan==wan: raise ValueError("LAN e WAN devono essere interfacce diverse.")
    prefix=ipaddress.IPv4Network(network.validate_prefix(plan["prefix"]))
    gateway=network.validate_gateway(plan["gateway"],prefix)
    external_routes=[r for r in inventory.get("routes",[]) if r.get("DestinationPrefix")=="0.0.0.0/0" and r.get("InterfaceAlias")==wan]
    if not external_routes:
        raise ValueError("La WAN selezionata non ha una route predefinita. Configura prima la connettività WAN.")
    if inventory.get("nats"):
        raise ValueError("WinNAT preesistenti: rimuovili esplicitamente prima di creare il nuovo.")
    if any(i.get("SharingEnabled") for i in inventory.get("icsConnections",[])):
        raise ValueError("Condivisione ICS già attiva: disabilitarla esplicitamente prima del setup WinNAT.")
    return lan,wan,prefix,gateway

def apply_profile(plan, inventory):
    lan,wan,prefix,gateway=preflight(plan,inventory)
    existing_ip=any(i.get("InterfaceAlias")==lan and i.get("IPAddress")==gateway and int(i.get("PrefixLength") or 0)==prefix.prefixlen for i in inventory.get("ips",[]))
    # Keep WAN's IP and default route intact. Use the target interface names to avoid
    # modifying a different adapter if an interface is renamed between steps.
    script=f"""
$ErrorActionPreference='Stop'
$lan={quote(lan)}
$wan={quote(wan)}
if(-not (Get-NetAdapter -Name $lan -ErrorAction Stop)) {{throw 'LAN non disponibile'}}
if(-not (Get-NetAdapter -Name $wan -ErrorAction Stop)) {{throw 'WAN non disponibile'}}
if(-not (Get-NetRoute -InterfaceAlias $wan -DestinationPrefix '0.0.0.0/0' -AddressFamily IPv4 -ErrorAction SilentlyContinue)) {{throw 'WAN senza default route'}}
if(@(Get-NetNat).Count -gt 0) {{throw 'WinNAT gia presente'}}
$ip={quote(gateway)}
if(-not (Get-NetIPAddress -InterfaceAlias $lan -IPAddress $ip -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {{$_.PrefixLength -eq {prefix.prefixlen}}})) {{
    New-NetIPAddress -InterfaceAlias $lan -IPAddress $ip -PrefixLength {prefix.prefixlen} -ErrorAction Stop | Out-Null
}}
Set-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop
New-NetNat -Name 'WinNAT-UI' -InternalIPInterfaceAddressPrefix {quote(str(prefix))} -ErrorAction Stop | Out-Null
"""
    network.ps(script)
    return {"lan":lan,"wan":wan,"prefix":str(prefix),"gateway":gateway,"existing_ip":existing_ip}

def matching_resources(inventory, scope):
    """Return an exact, selectable deletion plan; never infer ownership."""
    aliases=set(scope.get("interfaces",[]))
    valid={a.get("Name") for a in inventory.get("adapters",[])}
    if aliases-valid: raise ValueError("Interfaccia non presente: "+",".join(sorted(aliases-valid)))
    nat_names=set(scope.get("nat_names",[]))
    nats={n["Name"]:n for n in inventory.get("nats",[])}
    if nat_names-set(nats): raise ValueError("Una regola NAT non esiste più.")
    addresses=[i for i in inventory.get("ips",[]) if i.get("InterfaceAlias") in aliases and i.get("AddressState")!="Tentative"]
    routes=[r for r in inventory.get("routes",[]) if r.get("InterfaceAlias") in aliases and r.get("DestinationPrefix")!="0.0.0.0/0"]
    return {"nats":[nats[n] for n in sorted(nat_names)],"addresses":addresses if scope.get("remove_ips") else [],"routes":routes if scope.get("remove_routes") else [],"forwarding":sorted(aliases) if scope.get("disable_forwarding") else []}

def remove_selected(scope, inventory):
    """Remove selected resources regardless of creator; avoid WAN default route by design."""
    resources=matching_resources(inventory,scope)
    script=["$ErrorActionPreference='Stop'"]
    for nat in resources["nats"]:
        script.append(f"Remove-NetNat -Name {quote(nat['Name'])} -Confirm:$false -ErrorAction Stop")
    for route in resources["routes"]:
        dest=route.get("DestinationPrefix")
        hop=route.get("NextHop")
        idx=route.get("InterfaceIndex")
        if dest and hop and idx is not None:
            script.append(f"Get-NetRoute -InterfaceIndex {int(idx)} -DestinationPrefix {quote(dest)} -NextHop {quote(hop)} -ErrorAction Stop | Remove-NetRoute -Confirm:$false -ErrorAction Stop")
    for ip in resources["addresses"]:
        if ip.get("IPAddress") and ip.get("InterfaceIndex") is not None:
            script.append(f"Get-NetIPAddress -InterfaceIndex {int(ip['InterfaceIndex'])} -IPAddress {quote(ip['IPAddress'])} -AddressFamily IPv4 -ErrorAction Stop | Where-Object {{$_.PrefixLength -eq {int(ip['PrefixLength'])}}} | Remove-NetIPAddress -Confirm:$false -ErrorAction Stop")
    for alias in resources["forwarding"]:
        script.append(f"Set-NetIPInterface -InterfaceAlias {quote(alias)} -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop")
    if len(script)==1: raise ValueError("Nessuna risorsa selezionata.")
    network.ps("\n".join(script))
    return resources

def preview(resources):
    rows=[]
    rows.extend("Elimina NAT: "+str(n.get("Name"))+" ("+str(n.get("InternalIPInterfaceAddressPrefix"))+")" for n in resources["nats"])
    rows.extend("Elimina route: "+str(r.get("DestinationPrefix"))+" via "+str(r.get("NextHop"))+" su "+str(r.get("InterfaceAlias")) for r in resources["routes"])
    rows.extend("Elimina IP: "+str(i.get("IPAddress"))+"/"+str(i.get("PrefixLength"))+" su "+str(i.get("InterfaceAlias")) for i in resources["addresses"])
    rows.extend("Disabilita IPv4 forwarding: "+name for name in resources["forwarding"])
    return rows
