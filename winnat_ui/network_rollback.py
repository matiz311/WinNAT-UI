"""Best-effort, scoped compensation for failed Windows network commits.

This is not a Windows transaction. Restore only resources owned by the failed
operation, verify the observed final state and never report success on partial
restoration. The original error and snapshot remain available.
"""
import ipaddress
import json
from . import network
from . import network_guide


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def enabled(value):
    return str(value).lower() in ("1", "true", "enabled")


def scope_for(kind, args, before):
    """Bound potential rollback writes to affected adapters and NAT objects."""
    scope = {"interfaces": set(), "ips": set(), "routes": set(),
             "nats": set(), "router": False, "dhcp": set(), "metrics": set(),
             "forwarding": set(), "notes": [], "nat_rebuild": False}
    if kind == "guide":
        action, profile = args[0], args[1]
        wans = {w["alias"] for w in network_guide.wan_list(profile)}
        involved = {profile["lan"]} | wans
        scope["interfaces"] = involved
        scope["forwarding"] = set(involved)
        scope["router"] = True
        scope["nats"] = {n["Name"] for n in before.get("nats", [])} | {profile["nat"]}
        scope["nat_rebuild"] = action == "apply"
        if action in ("apply", "reset"):
            scope["ips"].add(profile["lan"])
            scope["routes"].add(profile["lan"])
            scope["dhcp"].add(profile["lan"])
        if action in ("apply", "reset"):
            scope["metrics"].update(wans)
    elif kind in ("add", "remove"):
        # Add NAT creates a resource under the requested name only. A failed
        # commit must never roll back or rebuild unrelated existing NATs.
        scope["nats"].add(args[0])
    elif kind == "lan_ip":
        # Scope the compensation to the address(es) selected by the user,
        # never to unrelated primary/secondary IPv4s on the same interface.
        action, alias, ip, prefix, old_ip, old_prefix, index = args
        scope["ips"].add(alias)
        scope["ip_filter"] = {alias: {ip} | ({old_ip} if old_ip else set())}
    elif kind == "setup":
        scope["nat_rebuild"] = True
        scope["ips"].add(args[0])
        scope["forwarding"].add(args[0])
        scope["nats"].add("WinNAT-UI")
        scope["nats"].update(n["Name"] for n in before.get("nats", []))
    elif kind == "profile":
        scope["nat_rebuild"] = True
        scope["ips"].add(args[0]["lan"])
        scope["forwarding"].add(args[0]["lan"])
        scope["nats"].add("WinNAT-UI")
        scope["nats"].update(n["Name"] for n in before.get("nats", []))
    elif kind == "reset":
        selected = args[0]
        scope["nats"].update(selected.get("nat_names", []))
        names = set(selected.get("interfaces", []))
        if selected.get("remove_ips"):
            scope["ips"] = names.copy()
        if selected.get("remove_routes"):
            scope["routes"] = names.copy()
        if selected.get("disable_forwarding"):
            scope["forwarding"] = names.copy()
    elif kind == "teardown":
        state = network.managed_state()
        if state:
            scope["nats"].add(state["nat"])
            if state.get("added_ip"):
                scope["ips"].add(state["lan"])
    elif kind == "external_teardown":
        scope["nats"].update(args[3])
        if args[4]:
            scope["ips"].add(args[0])
    else:
        raise ValueError("Rollback non supportato per " + kind)
    scope["interfaces"].update(scope["ips"] | scope["routes"] | scope["metrics"] | scope["forwarding"])
    return scope


def address_rows(data, alias, selected=None):
    # APIPA is automatically assigned by Windows; it cannot reliably be
    # recreated as a static IP. Leave it for Windows to reallocate.
    result = set()
    for row in data.get("ips", []):
        if row.get("InterfaceAlias") != alias:
            continue
        ip = row.get("IPAddress")
        if selected is not None and ip not in selected:
            continue
        if not ip or ipaddress.ip_address(ip).is_link_local:
            continue
        result.add((ip, int(row["PrefixLength"])))
    return result


def nat_rows(data, selected):
    return {r["Name"]: r for r in data.get("nats", []) if r.get("Name") in selected}


def iface(data, name):
    return next((i for i in data.get("interfaces", []) if i.get("InterfaceAlias") == name), None)


def route_rows(data, alias):
    # Connected and broadcast routes are managed by the TCP/IP stack.
    result = set()
    for r in data.get("routes", []):
        if r.get("InterfaceAlias") != alias:
            continue
        prefix, hop = r.get("DestinationPrefix"), r.get("NextHop")
        if not prefix or not hop or hop in ("0.0.0.0", "::"):
            continue
        result.add((prefix, hop, int(r.get("RouteMetric") or 0)))
    return result


def signature(data, scope):
    value = {"nat": {}, "ip": {}, "dhcp": {}, "routes": {}, "iface": {}, "router": None}
    value["nat"] = {k: (v.get("InternalIPInterfaceAddressPrefix"), v.get("ExternalIPInterfaceAddressPrefix"))
                    for k, v in nat_rows(data, scope["nats"]).items()}
    for alias in scope["ips"]:
        selected = scope.get("ip_filter", {}).get(alias)
        value["ip"][alias] = sorted(address_rows(data, alias, selected))
        if selected is not None:
            value.setdefault("ip_skip", {})[alias] = sorted(
                (row["IPAddress"], int(row["PrefixLength"]),
                 str(row.get("SkipAsSource", "")).lower() in ("true", "1"))
                for row in data.get("ips", []) if row.get("InterfaceAlias") == alias
                and row.get("IPAddress") in selected)
    for alias in scope["dhcp"]:
        item = iface(data, alias)
        value["dhcp"][alias] = enabled(item["Dhcp"]) if item else None
    for alias in scope["routes"]:
        value["routes"][alias] = sorted(route_rows(data, alias))
    for alias in scope["metrics"] | scope["forwarding"]:
        item = iface(data, alias)
        if item is None:
            value["iface"][alias] = None
        else:
            value["iface"][alias] = {
                k: (enabled(item.get(k)) if k == "Forwarding" else int(item.get(k) or 0))
                for k in ("Forwarding", "AutomaticMetric", "InterfaceMetric")
                if k == "Forwarding" and alias in scope["forwarding"]
                or k != "Forwarding" and alias in scope["metrics"]}
    if scope["router"]:
        value["router"] = int(data.get("globalRouter") or 0)
    return value


def rollback(before, scope, backup_path):
    """Attempt bounded restoration; raise with ALL errors and differences if incomplete."""
    if not backup_path:
        raise RuntimeError("Rollback bloccato: snapshot pre-commit non disponibile.")
    # Fail closed if live inventory is unavailable: do not blindly replay writes.
    after = network.collect()
    target = signature(before, scope)
    actual = signature(after, scope)
    if target == actual:
        return "Rollback: nessuna differenza rilevata (nessuna modifica da annullare)."
    failures = []
    operations = []

    def run(label, script):
        try:
            network.ps("$ErrorActionPreference='Stop';\n" + script)
            operations.append("OK: " + label)
        except Exception as error:
            failures.append(label + ": " + str(error))
            operations.append("FALLITO: " + label)

    # Restore NAT objects without changing NATs outside the operation scope.
    target_nat = nat_rows(before, scope["nats"])
    after_nat = nat_rows(after, scope["nats"])
    for name in sorted(set(after_nat) - set(target_nat)):
        run("Elimina NAT aggiunto " + name,
            "Remove-NetNat -Name " + quote(name) + " -Confirm:$false -ErrorAction Stop")
    for name in sorted(set(target_nat) - set(after_nat)):
        rule = target_nat[name]
        prefix = rule.get("InternalIPInterfaceAddressPrefix")
        if not prefix:
            failures.append("NAT " + name + ": prefisso originale mancante")
            continue
        cmd = "New-NetNat -Name " + quote(name) + " -InternalIPInterfaceAddressPrefix " + quote(prefix)
        external = rule.get("ExternalIPInterfaceAddressPrefix")
        if external:
            cmd += " -ExternalIPInterfaceAddressPrefix " + quote(external)
        run("Ricrea NAT " + name, cmd + " -ErrorAction Stop | Out-Null")
        # Collect() does not include preexisting static NAT mappings.
        failures.append("NAT " + name + ": mapping statici originali non presenti nello snapshot; "
                        "verifica manuale obbligatoria")
    for name in sorted(set(target_nat) & set(after_nat)):
        original = target_nat[name]
        modified = after_nat[name]
        keys = ("InternalIPInterfaceAddressPrefix", "ExternalIPInterfaceAddressPrefix")
        if any(original.get(k) != modified.get(k) for k in keys):
            if scope.get("nat_rebuild") and original.get("InternalIPInterfaceAddressPrefix"):
                try:
                    script = network.nat_expansion_script(
                        original["InternalIPInterfaceAddressPrefix"], after, allow_restore=True)
                    run("Ripristina prefisso NAT " + name, script)
                except Exception as error:
                    failures.append("NAT " + name + ": impossibile predisporre ripristino: " + str(error))
            else:
                failures.append("NAT " + name + ": prefisso modificato, ripristino automatico non sicuro")

    # LAN address/DHCP state is restored only for selected interfaces.
    for alias in sorted(scope["ips"] | scope["dhcp"]):
        before_if = iface(before, alias)
        after_if = iface(after, alias)
        if before_if is None or after_if is None or before_if.get("InterfaceIndex") != after_if.get("InterfaceIndex"):
            failures.append("Interfaccia " + alias + ": assente o InterfaceIndex cambiato")
            continue
        original_dhcp = enabled(before_if.get("Dhcp"))
        current_dhcp = enabled(after_if.get("Dhcp"))
        if alias in scope["dhcp"] and original_dhcp and not current_dhcp:
            run(alias + ": ripristina DHCP", "& netsh.exe interface ipv4 set address "
                + quote("name=" + alias) + " source=dhcp store=persistent; "
                + "if ($LASTEXITCODE -ne 0) { throw 'netsh DHCP failed' }")
            continue
        selected = scope.get("ip_filter", {}).get(alias)
        original_ip = address_rows(before, alias, selected) if alias in scope["ips"] else set()
        current_ip = address_rows(after, alias, selected) if alias in scope["ips"] else set()
        if alias in scope["dhcp"] and not original_dhcp and current_dhcp:
            run(alias + ": disabilita DHCP", "Set-NetIPInterface -InterfaceAlias "
                + quote(alias) + " -AddressFamily IPv4 -Dhcp Disabled -ErrorAction Stop")
        for ip, prefix in sorted(current_ip - original_ip):
            run(alias + ": rimuovi IPv4 " + ip,
                "Remove-NetIPAddress -InterfaceAlias " + quote(alias) + " -IPAddress "
                + quote(ip) + " -AddressFamily IPv4 -Confirm:$false -ErrorAction Stop")
        for ip, prefix in sorted(original_ip - current_ip):
            original_row = next((row for row in before.get("ips", []) if
                                 row.get("InterfaceAlias") == alias and
                                 row.get("IPAddress") == ip and
                                 int(row.get("PrefixLength", -1)) == prefix), {})
            skip = str(original_row.get("SkipAsSource", "False")).lower() in ("true", "1")
            run(alias + ": ripristina IPv4 " + ip,
                "New-NetIPAddress -InterfaceAlias " + quote(alias) + " -IPAddress "
                + quote(ip) + " -PrefixLength " + str(prefix)
                + " -SkipAsSource $" + ("true" if skip else "false")
                + " -ErrorAction Stop | Out-Null")

    # Only restore explicitly selected non-connected routes.
    for alias in sorted(scope["routes"]):
        b = iface(before, alias)
        a = iface(after, alias)
        if not b or not a or b.get("InterfaceIndex") != a.get("InterfaceIndex"):
            failures.append("Route " + alias + ": interfaccia modificata")
            continue
        desired, present = route_rows(before, alias), route_rows(after, alias)
        for prefix, hop, metric in sorted(present - desired):
            run(alias + ": elimina route " + prefix,
                "Get-NetRoute -InterfaceAlias " + quote(alias) + " -DestinationPrefix "
                + quote(prefix) + " -NextHop " + quote(hop)
                + " -AddressFamily IPv4 -ErrorAction Stop | Where-Object {$_.RouteMetric -eq "
                + str(metric) + "} | Remove-NetRoute -Confirm:$false -ErrorAction Stop")
        for prefix, hop, metric in sorted(desired - present):
            run(alias + ": ripristina route " + prefix,
                "New-NetRoute -InterfaceAlias " + quote(alias) + " -DestinationPrefix "
                + quote(prefix) + " -NextHop " + quote(hop) + " -RouteMetric "
                + str(metric) + " -ErrorAction Stop | Out-Null")

    for alias in sorted(scope["forwarding"] | scope["metrics"]):
        b = iface(before, alias)
        a = iface(after, alias)
        if not b or not a or b.get("InterfaceIndex") != a.get("InterfaceIndex"):
            failures.append("Impostazioni " + alias + ": interfaccia modificata")
            continue
        if alias in scope["forwarding"] and enabled(b.get("Forwarding")) != enabled(a.get("Forwarding")):
            value = "Enabled" if enabled(b.get("Forwarding")) else "Disabled"
            run(alias + ": forwarding " + value,
                "Set-NetIPInterface -InterfaceAlias " + quote(alias)
                + " -AddressFamily IPv4 -Forwarding " + value + " -ErrorAction Stop")
        if alias in scope["metrics"] and (b.get("AutomaticMetric") != a.get("AutomaticMetric")
                                         or b.get("InterfaceMetric") != a.get("InterfaceMetric")):
            auto = "Enabled" if enabled(b.get("AutomaticMetric")) else "Disabled"
            command = "Set-NetIPInterface -InterfaceAlias " + quote(alias) + " -AddressFamily IPv4 -AutomaticMetric " + auto
            if auto == "Disabled":
                command += " -InterfaceMetric " + str(int(b.get("InterfaceMetric") or 0))
            run(alias + ": metriche", command + " -ErrorAction Stop")
    if scope["router"] and int(before.get("globalRouter") or 0) != int(after.get("globalRouter") or 0):
        run("Ripristina IPEnableRouter",
            "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters' "
            "-Name IPEnableRouter -Value " + str(int(before.get("globalRouter") or 0)) + " -ErrorAction Stop")

    try:
        final = network.collect()
        residual = {} if signature(final, scope) == target else {
            "atteso": target, "rilevato": signature(final, scope)}
    except Exception as error:
        residual = {"errore_verifica": str(error)}
    report = ("SNAPSHOT: " + str(backup_path) + "\n" +
              "OPERAZIONI:\n" + "\n".join(operations or ["Nessuna"]) + "\n" +
              "ERRORI:\n" + "\n".join(failures or ["Nessuno"]) + "\n" +
              "DIFFERENZE RESIDUE:\n" + json.dumps(residual, ensure_ascii=False, indent=2, default=str))
    if failures or residual:
        raise RuntimeError("ROLLBACK INCOMPLETO - ripristino manuale necessario\n" + report)
    return "ROLLBACK VERIFICATO - impostazioni monitorate ripristinate\n" + report
