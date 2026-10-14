"""Windows 11 IPv4 gateway profile from the user-provided NAT/Routing guide.

Candidate plans are explicit; execution requires a fresh inventory and confirmation.
No ownership metadata is required to reset NAT, LAN addresses, or routing settings.
"""
import ipaddress
import json
import network

DEFAULTS = {"lan": "Ethernet", "wans": [{"alias": "USB-C", "metric": 10}],
            "prefix": "10.10.10.0/24", "gateway": "10.10.10.1", "nat": "NAT-Firewall"}
DEFAULT_PREFIX, DEFAULT_GATEWAY = "10.10.10.0/24", "10.10.10.1"
METRIC_STEP = 40   # suggested metric gap between consecutive WANs


def wan_list(profile):
    """WANs in priority order as [{"alias", "metric"}]. Accepts the legacy
    wan1/metric1 + wan2/metric2 keys used by profiles saved before v1.9."""
    if "wans" in profile:
        raw = profile.get("wans") or []
    else:
        raw = [{"alias": profile.get("wan1", ""), "metric": profile.get("metric1", 10)},
               {"alias": profile.get("wan2", ""), "metric": profile.get("metric2", 50)}]
    wans = []
    for item in raw:
        alias = str(item.get("alias", "")).strip()
        if alias:
            wans.append({"alias": alias, "metric": item.get("metric", "")})
    return wans


def suggest_metric(wans):
    metrics = [int(w["metric"]) for w in wans if str(w.get("metric", "")).strip().isdigit()]
    return min(9999, (max(metrics) + METRIC_STEP) if metrics else 10)


def detect_lan_subnet(data, alias):
    """Subnet currently on the LAN adapter, kept as the static LAN network.

    Returns {"prefix", "gateway", "source", "origin"}: source is "rilevata" when
    a usable IPv4 exists on the interface (manual addresses preferred over DHCP),
    otherwise "predefinita" with 10.10.10.0/24 and 10.10.10.1.
    """
    candidates = []
    for ip in data.get("ips", []):
        if ip.get("InterfaceAlias") != alias:
            continue
        try:
            iface = ipaddress.IPv4Interface("%s/%s" % (ip.get("IPAddress"), ip.get("PrefixLength")))
        except (ValueError, TypeError):
            continue
        net = iface.network
        if iface.ip.is_link_local or iface.ip.is_loopback or not 8 <= net.prefixlen <= 30:
            continue
        if iface.ip in (net.network_address, net.broadcast_address):
            continue
        origin = str(ip.get("PrefixOrigin") or "")
        candidates.append((0 if origin == "Manual" else 1, str(net), str(iface.ip), origin))
    if candidates:
        _rank, prefix, gateway, origin = sorted(candidates)[0]
        return {"prefix": prefix, "gateway": gateway, "source": "rilevata", "origin": origin}
    return {"prefix": DEFAULT_PREFIX, "gateway": DEFAULT_GATEWAY, "source": "predefinita", "origin": ""}


def wan_networks(data, aliases):
    nets = []
    for ip in data.get("ips", []):
        if ip.get("InterfaceAlias") in aliases:
            try:
                nets.append((ip.get("InterfaceAlias"), ipaddress.IPv4Interface(
                    "%s/%s" % (ip.get("IPAddress"), ip.get("PrefixLength"))).network))
            except (ValueError, TypeError):
                pass
    return nets


def psquote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _names(data):
    return {a["Name"] for a in data.get("adapters", [])}


def _iface(data, alias):
    for i in data.get("interfaces", []):
        if i.get("InterfaceAlias") == alias:
            return i
    raise ValueError("Interfaccia IPv4 non disponibile: " + alias)


def validate(profile, data, action):
    if action not in ("apply", "disable", "reset"):
        raise ValueError("Operazione sconosciuta.")
    lan = str(profile.get("lan", "")).strip()
    wans = wan_list(profile)
    if not lan:
        raise ValueError("Seleziona l'interfaccia LAN.")
    if not wans:
        raise ValueError("Seleziona almeno una WAN.")
    aliases = [lan] + [w["alias"] for w in wans]
    if len(set(aliases)) != len(aliases):
        raise ValueError("Seleziona interfacce LAN e WAN distinte.")
    if any(a not in _names(data) for a in aliases):
        raise ValueError("Almeno un'interfaccia non è presente sul PC.")
    for a in aliases:
        _iface(data, a)
    prefix = ipaddress.IPv4Network(network.validate_prefix(profile.get("prefix", "")))
    gateway = network.validate_gateway(profile.get("gateway", ""), prefix)
    nat = network.validate_name(profile.get("nat", "NAT-Firewall"))
    previous = 0
    for i, w in enumerate(wans):
        try:
            w["metric"] = int(w["metric"])
        except (TypeError, ValueError):
            raise ValueError("Metrica non valida per la WAN " + w["alias"] + ".")
        if not 1 <= w["metric"] <= 9999:
            raise ValueError("Le metriche devono essere comprese tra 1 e 9999.")
        if w["metric"] <= previous:
            raise ValueError("Le metriche devono crescere secondo la priorità: " + w["alias"]
                             + " deve avere una metrica maggiore di " + str(previous) + ".")
        previous = w["metric"]
    for alias, net in (wan_networks(data, [w["alias"] for w in wans]) if action == "apply" else []):
        if net.overlaps(prefix):
            raise ValueError("La subnet LAN " + str(prefix) + " si sovrappone alla rete della WAN "
                             + alias + " (" + str(net) + "): scegli un'altra subnet.")
    normalized = dict(lan=lan, wans=wans, prefix=str(prefix), gateway=gateway, nat=nat)
    if action == "apply":
        if data.get("nats"):
            raise ValueError("WinNAT esistente: usa Ripristina o elimina le regole prima di applicare il profilo.")
        if any(c.get("SharingEnabled") for c in data.get("icsConnections", [])):
            raise ValueError("ICS attivo: disabilita la condivisione prima di usare WinNAT.")
        if any(c.get("Error") for c in data.get("icsConnections", [])):
            raise ValueError("Stato ICS non verificabile: operazione bloccata.")
        for i, w in enumerate(wans):
            if not any(r.get("InterfaceAlias") == w["alias"] and r.get("DestinationPrefix") == "0.0.0.0/0"
                       for r in data.get("routes", [])):
                raise ValueError(("WAN primaria " if i == 0 else "WAN ") + w["alias"] +
                                 " senza default route: collegala a Internet o rimuovila dalla configurazione.")
    return normalized


def _wan_aliases(p):
    return [w["alias"] for w in wan_list(p)]


def _on_lan(data, profile):
    lan = profile["lan"]
    return ([p for p in data.get("ips", []) if p.get("InterfaceAlias") == lan],
            [r for r in data.get("routes", []) if r.get("InterfaceAlias") == lan])


def preview(action, profile, data):
    p = validate(profile, data, action)
    lan_ips, lan_routes = _on_lan(data, p)
    involved = [p["lan"]] + _wan_aliases(p)
    names = [n.get("Name") for n in data.get("nats", [])]
    if action == "apply":
        items = [
            "LAN " + p["lan"] + ": DHCP IPv4 disabilitato",
            "LAN: sostituisce gli indirizzi IPv4 esistenti con un unico indirizzo statico persistente (netsh)",
            "LAN: rimuove il vecchio default gateway e le route instradate residue (" + str(len(lan_routes)) + " route rilevate)",
            "LAN: configura " + p["gateway"] + "/" + p["prefix"].split("/")[1] + " senza gateway",
            "Routing globale: IPEnableRouter = 1 (riavvio raccomandato)",
            "Forwarding IPv4: abilita su " + ", ".join(involved),
        ]
        for i, w in enumerate(p["wans"]):
            items.append(("WAN primaria " if i == 0 else "WAN " + str(i + 1) + " ") + w["alias"]
                         + ": metrica " + str(w["metric"]))
        items.append("Crea NAT " + p["nat"] + " per " + p["prefix"])
        items.append("WAN: DHCP, gateway e DNS esistenti NON vengono modificati.")
    elif action == "disable":
        items = ["Elimina tutti gli oggetti WinNAT (" + str(len(names)) + "): " + (", ".join(names) or "nessuno"),
                 "Forwarding IPv4: disabilita su " + ", ".join(involved),
                 "Routing globale: IPEnableRouter = 0 (riavvio raccomandato)",
                 "Conserva IP LAN, route, DHCP e metriche WAN."]
    else:
        items = ["Elimina tutti gli oggetti WinNAT (" + str(len(names)) + "): " + (", ".join(names) or "nessuno"),
                 "LAN " + p["lan"] + ": elimina " + str(len(lan_ips)) + " indirizzi IPv4",
                 "LAN: elimina " + str(len(lan_routes)) + " route, incluse eventuali default route",
                 "LAN: ripristina DHCP IPv4 abilitato",
                 "Forwarding IPv4: disabilita su " + ", ".join(involved),
                 "WAN: ripristina metriche automatiche sulle interfacce selezionate",
                 "Routing globale: IPEnableRouter = 0 (riavvio raccomandato)",
                 "Conserva indirizzi, gateway, DHCP e DNS delle WAN."]
    items.append("ATTENZIONE: le modifiche possono interrompere connessioni e sessioni remote; backup prima del commit.")
    return items


def fingerprint_state(profile, data):
    """Stable, safety-relevant properties of the selected gateway profile."""
    aliases = {profile["lan"], *_wan_aliases(profile)}
    def ordered(rows):
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))
    adapters = ordered([
        {"Name": a.get("Name"), "InterfaceIndex": a.get("InterfaceIndex")}
        for a in data.get("adapters", []) if a.get("Name") in aliases
    ])
    ips = ordered([
        {"InterfaceAlias": ip.get("InterfaceAlias"), "InterfaceIndex": ip.get("InterfaceIndex"),
         "IPAddress": ip.get("IPAddress"), "PrefixLength": ip.get("PrefixLength")}
        for ip in data.get("ips", [])
        if ip.get("InterfaceAlias") == profile["lan"]
        and not str(ip.get("IPAddress", "")).startswith("169.254.")
    ])
    routes = ordered([
        {"InterfaceAlias": r.get("InterfaceAlias"), "InterfaceIndex": r.get("InterfaceIndex"),
         "DestinationPrefix": r.get("DestinationPrefix"), "NextHop": r.get("NextHop"),
         "RouteMetric": r.get("RouteMetric")}
        for r in data.get("routes", [])
        if ((r.get("InterfaceAlias") == profile["lan"] and
             (r.get("DestinationPrefix") == "0.0.0.0/0" or
              r.get("NextHop") not in ("0.0.0.0", "::", None)))
            or (r.get("InterfaceAlias") in aliases - {profile["lan"]}
                and r.get("DestinationPrefix") == "0.0.0.0/0"))
    ])
    interfaces = ordered([
        {"InterfaceAlias": i.get("InterfaceAlias"), "InterfaceIndex": i.get("InterfaceIndex"),
         "Dhcp": i.get("Dhcp"), "Forwarding": i.get("Forwarding"),
         "AutomaticMetric": i.get("AutomaticMetric"), "InterfaceMetric": i.get("InterfaceMetric")}
        for i in data.get("interfaces", []) if i.get("InterfaceAlias") in aliases
    ])
    nats = ordered([
        {"Name": n.get("Name"), "InternalIPInterfaceAddressPrefix": n.get("InternalIPInterfaceAddressPrefix"),
         "ExternalIPInterfaceAddressPrefix": n.get("ExternalIPInterfaceAddressPrefix")}
        for n in data.get("nats", [])
    ])
    ics = ordered([
        {"Name": c.get("Name"), "SharingEnabled": c.get("SharingEnabled"),
         "SharingConnectionType": c.get("SharingConnectionType"), "Error": c.get("Error")}
        for c in data.get("icsConnections", [])
    ])
    return {"adapters": adapters, "ips": ips, "routes": routes, "ifaces": interfaces,
            "nats": nats, "global": data.get("globalRouter"), "ics": ics}


def fingerprint(profile, data):
    """Optimistic concurrency on properties relevant to the requested change."""
    return json.dumps(fingerprint_state(profile, data), sort_keys=True, default=str)


def fingerprint_differences(expected, actual):
    """Enumerate changed groups for the expandable diagnostics panel."""
    try:
        before = json.loads(expected)
        after = json.loads(actual)
    except (ValueError, TypeError):
        return ["Impronta precedente non valida."]
    return [
        key + ": anteprima=" + json.dumps(before.get(key), ensure_ascii=False, default=str)
        + "; attuale=" + json.dumps(after.get(key), ensure_ascii=False, default=str)
        for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)
    ]



def _guard_script(p):
    """Bind $lan, $wan1..$wanN and refuse to run if two names share an adapter."""
    lines = ["", "$ErrorActionPreference = 'Stop'", "$lan = " + psquote(p["lan"])]
    for i, alias in enumerate(_wan_aliases(p), 1):
        lines.append("$wan%d = %s" % (i, psquote(alias)))
    names = ["$lan"] + ["$wan%d" % i for i in range(1, len(p["wans"]) + 1)]
    lines += [
        "$lanIndex = (Get-NetAdapter -Name $lan -ErrorAction Stop).ifIndex",
        "$indexes = @(" + ", ".join("(Get-NetAdapter -Name %s -ErrorAction Stop).ifIndex" % n for n in names) + ")",
        "if (@($indexes | Select-Object -Unique).Count -ne $indexes.Count) { throw 'Interfacce LAN/WAN duplicate' }",
        ""]
    return "\n".join(lines)


def execute(action, profile, current, expected_fingerprint):
    p = validate(profile, current, action)
    actual_fingerprint = fingerprint(p, current)
    if actual_fingerprint != expected_fingerprint:
        differences = fingerprint_differences(expected_fingerprint, actual_fingerprint)
        raise ValueError("Configurazione rilevante modificata dopo l'anteprima. "
                         "Aggiorna e prepara nuovamente.\nDifferenze:\n"
                         + "\n".join(differences))

    # Save a diagnostic snapshot (not a transactional rollback).
    backup = network.snapshot(current)
    script = [_guard_script(p)]
    lan = "$lan"
    if action == "apply":
        # The guide deliberately replaces ALL IPv4 LAN configuration, but never WAN IPs.
        script += [
            "if (@(Get-NetNat).Count -gt 0) { throw 'NAT preesistente: esegui prima Ripristina' }",
            # Windows can retain DHCP=Enabled in PersistentStore even after
            # Set-NetIPInterface -Dhcp Disabled. New-NetIPAddress then raises
            # "Inconsistent parameters PolicyStore PersistentStore and Dhcp Enabled".
            # netsh 'set address' changes the static source and IP persistently
            # in one operation, removing previous interface IPs/default gateway.
            "$lanIP = %s" % psquote(p["gateway"]),
            "$lanMask = %s" % psquote(str(ipaddress.IPv4Network(p["prefix"]).netmask)),
            "$lanPrefix = %d" % ipaddress.IPv4Network(p["prefix"]).prefixlen,
            # Detect actual address conflict, not just a localized netsh string.
            "$duplicate = @(Get-NetIPAddress -AddressFamily IPv4 -IPAddress $lanIP -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InterfaceIndex -ne $lanIndex })",
            "if ($duplicate.Count -gt 0) { throw ('IP LAN ' + $lanIP + ' già assegnato ad altre interfacce: ' + "
            "(($duplicate | ForEach-Object { $_.InterfaceAlias + ' (ifIndex ' + $_.InterfaceIndex + ')' }) -join ', ')) }",
            "$lanAddresses = @(Get-NetIPAddress -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction SilentlyContinue)",
            "$iface = Get-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction Stop",
            # If LAN already has precisely the requested static IP, netsh is unnecessary.
            "$alreadyConfigured = ($iface.Dhcp -eq 'Disabled' -and $lanAddresses.Count -eq 1 -and "
            "@($lanAddresses | Where-Object { $_.IPAddress -eq $lanIP -and $_.PrefixLength -eq $lanPrefix }).Count -eq 1)",
            "$netshExitCode = 0",
            "$netshOutput = @()",
            "if (-not $alreadyConfigured) {",
            "  $netshOutput = & netsh.exe interface ipv4 set address "
            '("name=" + $lan) "source=static" ("address=" + $lanIP) '
            '("mask=" + $lanMask) "gateway=none" "store=persistent" 2>&1',
            "  $netshExitCode = $LASTEXITCODE",
            "}",
            # A nonzero netsh status can coexist with an already-applied change:
            # decide by inspecting effective state, never by error text.
            "$iface = Get-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction Stop",
            "$lanAddresses = @(Get-NetIPAddress -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction SilentlyContinue)",
            "$configuredIP = @($lanAddresses | Where-Object { $_.IPAddress -eq $lanIP -and $_.PrefixLength -eq $lanPrefix })",
            "$validState = ($iface.Dhcp -eq 'Disabled' -and $configuredIP.Count -eq 1 -and $lanAddresses.Count -eq 1)",
            "if (-not $validState) {",
            "  $addressSummary = ($lanAddresses | ForEach-Object { $_.IPAddress + '/' + $_.PrefixLength }) -join ', '",
            "  throw ('Impossibile impostare IP statico LAN tramite netsh (codice ' + $netshExitCode + '). ' + "
            "'DHCP=' + $iface.Dhcp + '; IPv4 rilevati=[' + $addressSummary + ']; atteso=' + $lanIP + '/' + "
            "$lanPrefix + '. Output: ' + ($netshOutput | Out-String))",
            "}",
            # netsh clears previous IPs and default gateway; remove any leftover
            # routed entries while preserving the new connected/on-link route.
            "Get-NetRoute -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
            "Where-Object { $_.DestinationPrefix -eq '0.0.0.0/0' -or $_.NextHop -notin @('0.0.0.0', '::') } | "
            "Remove-NetRoute -Confirm:$false -ErrorAction Stop",
            "Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters' -Name IPEnableRouter -Value 1 -ErrorAction Stop",
            "Set-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop",
        ]
        for i, w in enumerate(p["wans"], 1):
            script += ["Set-NetIPInterface -InterfaceAlias $wan%d -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop" % i,
                       "Set-NetIPInterface -InterfaceAlias $wan%d -AddressFamily IPv4 -InterfaceMetric %d -ErrorAction Stop"
                       % (i, w["metric"])]
        script.append("New-NetNat -Name %s -InternalIPInterfaceAddressPrefix %s -ErrorAction Stop | Out-Null"
                      % (psquote(p["nat"]), psquote(p["prefix"])))
    else:
        script += [
            # Unrestricted by creator: every existing WinNAT is removed as explicitly previewed.
            "Get-NetNat -ErrorAction Stop | Remove-NetNat -Confirm:$false -ErrorAction Stop",
            "Set-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop",
        ]
        for i in range(1, len(p["wans"]) + 1):
            script.append("Set-NetIPInterface -InterfaceAlias $wan%d -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop" % i)
        if action == "reset":
            for i in range(1, len(p["wans"]) + 1):
                script.append("Set-NetIPInterface -InterfaceAlias $wan%d -AddressFamily IPv4 -AutomaticMetric Enabled -ErrorAction Stop" % i)
            script += [
                # Reset all manually configured addresses/default gateway
                # while setting DHCP, without an intermediate inconsistent store.
                "$lanDhcp = (Get-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction Stop).Dhcp",
                "if ($lanDhcp -ne 'Enabled') {",
                "  $netshOutput = & netsh.exe interface ipv4 set address "
                '("name=" + $lan) "source=dhcp" "store=persistent" 2>&1',
                "  $netshExitCode = $LASTEXITCODE",
                "  $lanDhcp = (Get-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction Stop).Dhcp",
                "  if ($lanDhcp -ne 'Enabled') { throw ('Impossibile ripristinare DHCP LAN tramite netsh (codice ' + $netshExitCode + '): ' + ($netshOutput | Out-String)) }",
                "}",
                "if ((Get-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction Stop).Dhcp -ne 'Enabled') { throw 'LAN: DHCP IPv4 non attivo dopo il ripristino.' }",
                "Get-NetRoute -InterfaceAlias $lan -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                "Where-Object { $_.NextHop -notin @('0.0.0.0', '::') -and $_.DestinationPrefix -ne '0.0.0.0/0' } | "
                "Remove-NetRoute -Confirm:$false -ErrorAction Stop",
            ]
        script.append("Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters' -Name IPEnableRouter -Value 0 -ErrorAction Stop")
    # A single PowerShell invocation makes operation order clear, but not atomic.
    try:
        result = network.ps("\n".join(script))
    except Exception as error:
        # The operation is not atomic; gather a NEW read-only inventory after
        # failure without hiding the original error if diagnostics also fail.
        try:
            after = network.collect()
            after_text = json.dumps(after, indent=2, ensure_ascii=False, default=str)
        except Exception as inventory_error:
            after_text = ("Impossibile rilevare lo stato successivo: "
                          + repr(inventory_error))
        details = (
            "OPERAZIONE GUIDATA FALLITA\n"
            "Azione: " + action + "\n"
            "Interfaccia LAN: " + p["lan"] + "\n"
            "WAN (in ordine di priorità): " + ", ".join(
                w["alias"] + " [metrica " + str(w["metric"]) + "]" for w in p["wans"]) + "\n"
            "IPv4 atteso: " + p["gateway"] + "/" + p["prefix"].split("/")[1] + "\n"
            "NAT atteso: " + p["nat"] + "\n\n"
            "ERRORE ORIGINALE:\n" + str(error) + "\n\n"
            "CONFIGURAZIONE RILEVATA PRIMA DEL COMMIT:\n"
            + json.dumps(current, indent=2, ensure_ascii=False, default=str) + "\n\n"
            "CONFIGURAZIONE RILEVATA DOPO L'ERRORE:\n" + after_text + "\n\n"
            "ATTENZIONE: nessun rollback automatico; verificare lo stato prima di riprovare."
        )
        raise RuntimeError(details) from error
    if action == "reset" and network.managed_state():
        network.state_path().unlink(missing_ok=True)
    return {"backup": backup, "output": result, "action": action}
