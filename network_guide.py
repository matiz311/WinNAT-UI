"""Windows 11 IPv4 gateway profile from the user-provided NAT/Routing guide.

Candidate plans are explicit; execution requires a fresh inventory and confirmation.
No ownership metadata is required to reset NAT, LAN addresses, or routing settings.
"""
import ipaddress
import json
import network

DEFAULTS = {"lan": "Ethernet", "wan1": "USB-C", "wan2": "Wi-Fi",
            "prefix": "10.10.10.0/24", "gateway": "10.10.10.1",
            "nat": "NAT-Firewall", "metric1": 10, "metric2": 50}


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
    wan1 = str(profile.get("wan1", "")).strip()
    wan2 = str(profile.get("wan2", "")).strip()
    if not lan or not wan1 or len({lan, wan1, wan2} - {""}) != len([x for x in (lan, wan1, wan2) if x]):
        raise ValueError("Seleziona interfacce LAN e WAN distinte.")
    aliases = [lan, wan1] + ([wan2] if wan2 else [])
    if any(a not in _names(data) for a in aliases):
        raise ValueError("Almeno un'interfaccia non è presente sul PC.")
    for a in aliases:
        _iface(data, a)
    prefix = ipaddress.IPv4Network(network.validate_prefix(profile.get("prefix", "")))
    gateway = network.validate_gateway(profile.get("gateway", ""), prefix)
    nat = network.validate_name(profile.get("nat", "NAT-Firewall"))
    m1, m2 = int(profile.get("metric1", 10)), int(profile.get("metric2", 50))
    if not 1 <= m1 <= 9999 or not 1 <= m2 <= 9999 or (wan2 and m1 >= m2):
        raise ValueError("Le metriche devono essere 1-9999, con primaria inferiore alla secondaria.")
    normalized = dict(lan=lan, wan1=wan1, wan2=wan2, prefix=str(prefix),
                      gateway=gateway, nat=nat, metric1=m1, metric2=m2)
    if action == "apply":
        if data.get("nats"):
            raise ValueError("WinNAT esistente: usa Ripristina o elimina le regole prima di applicare il profilo.")
        if any(c.get("SharingEnabled") for c in data.get("icsConnections", [])):
            raise ValueError("ICS attivo: disabilita la condivisione prima di usare WinNAT.")
        if any(c.get("Error") for c in data.get("icsConnections", [])):
            raise ValueError("Stato ICS non verificabile: operazione bloccata.")
        if not any(r.get("InterfaceAlias") == wan1 and r.get("DestinationPrefix") == "0.0.0.0/0"
                   for r in data.get("routes", [])):
            raise ValueError("WAN primaria senza default route. Collega la WAN a Internet prima del commit.")
        for w in [wan2] if wan2 else []:
            if not any(r.get("InterfaceAlias") == w and r.get("DestinationPrefix") == "0.0.0.0/0"
                       for r in data.get("routes", [])):
                raise ValueError("WAN secondaria senza default route. Deselezionala oppure collegala.")
    return normalized


def _on_lan(data, profile):
    lan = profile["lan"]
    return ([p for p in data.get("ips", []) if p.get("InterfaceAlias") == lan],
            [r for r in data.get("routes", []) if r.get("InterfaceAlias") == lan])


def preview(action, profile, data):
    p = validate(profile, data, action)
    lan_ips, lan_routes = _on_lan(data, p)
    involved = [p["lan"], p["wan1"]] + ([p["wan2"]] if p["wan2"] else [])
    names = [n.get("Name") for n in data.get("nats", [])]
    if action == "apply":
        items = [
            "LAN " + p["lan"] + ": DHCP IPv4 disabilitato",
            "LAN: sostituisce gli indirizzi IPv4 esistenti con un unico indirizzo statico persistente (netsh)",
            "LAN: rimuove il vecchio default gateway e le route instradate residue (" + str(len(lan_routes)) + " route rilevate)",
            "LAN: configura " + p["gateway"] + "/" + p["prefix"].split("/")[1] + " senza gateway",
            "Routing globale: IPEnableRouter = 1 (riavvio raccomandato)",
            "Forwarding IPv4: abilita su " + ", ".join(involved),
            "WAN primaria " + p["wan1"] + ": metrica " + str(p["metric1"]),
        ]
        if p["wan2"]:
            items.append("WAN secondaria " + p["wan2"] + ": metrica " + str(p["metric2"]))
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


def fingerprint(profile, data):
    """Optimistic concurrency check on exactly the settings this profile changes."""
    p = profile
    aliases = {p["lan"], p["wan1"], p["wan2"]} - {""}
    def order(values):
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return json.dumps({
        "adapters": order([i for i in data.get("adapters", []) if i.get("Name") in aliases]),
        "ips": order([i for i in data.get("ips", []) if i.get("InterfaceAlias") == p["lan"]]),
        "routes": order([i for i in data.get("routes", []) if i.get("InterfaceAlias") in aliases]),
        "ifaces": order([i for i in data.get("interfaces", []) if i.get("InterfaceAlias") in aliases]),
        "nats": order(data.get("nats", [])),
        "global": data.get("globalRouter"),
        "ics": order(data.get("icsConnections", []))
    }, sort_keys=True, default=str)


def _guard_script(p):
    return """
$ErrorActionPreference = 'Stop'
$lan = %s
$wan1 = %s
$wan2 = %s
$lanIndex = (Get-NetAdapter -Name $lan -ErrorAction Stop).ifIndex
$wanIndex = (Get-NetAdapter -Name $wan1 -ErrorAction Stop).ifIndex
if ($lanIndex -eq $wanIndex) { throw 'LAN e WAN coincidono' }
if ($wan2) {
    $wan2Index = (Get-NetAdapter -Name $wan2 -ErrorAction Stop).ifIndex
    if ($wan2Index -eq $lanIndex -or $wan2Index -eq $wanIndex) { throw 'Interfacce duplicate' }
}
""" % (psquote(p["lan"]), psquote(p["wan1"]), psquote(p["wan2"]))


def execute(action, profile, current, expected_fingerprint):
    p = validate(profile, current, action)
    if fingerprint(p, current) != expected_fingerprint:
        raise ValueError("Configurazione modificata dopo l'anteprima. Aggiorna e prepara nuovamente.")
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
            "Set-NetIPInterface -InterfaceAlias $wan1 -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop",
            "Set-NetIPInterface -InterfaceAlias $wan1 -AddressFamily IPv4 -InterfaceMetric %d -ErrorAction Stop" % p["metric1"],
        ]
        if p["wan2"]:
            script += ["Set-NetIPInterface -InterfaceAlias $wan2 -AddressFamily IPv4 -Forwarding Enabled -ErrorAction Stop",
                       "Set-NetIPInterface -InterfaceAlias $wan2 -AddressFamily IPv4 -InterfaceMetric %d -ErrorAction Stop" % p["metric2"]]
        script.append("New-NetNat -Name %s -InternalIPInterfaceAddressPrefix %s -ErrorAction Stop | Out-Null"
                      % (psquote(p["nat"]), psquote(p["prefix"])))
    else:
        script += [
            # Unrestricted by creator: every existing WinNAT is removed as explicitly previewed.
            "Get-NetNat -ErrorAction Stop | Remove-NetNat -Confirm:$false -ErrorAction Stop",
            "Set-NetIPInterface -InterfaceAlias $lan -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop",
            "Set-NetIPInterface -InterfaceAlias $wan1 -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop",
        ]
        if p["wan2"]:
            script.append("Set-NetIPInterface -InterfaceAlias $wan2 -AddressFamily IPv4 -Forwarding Disabled -ErrorAction Stop")
        if action == "reset":
            script += [
                "Set-NetIPInterface -InterfaceAlias $wan1 -AddressFamily IPv4 -AutomaticMetric Enabled -ErrorAction Stop",
            ]
            if p["wan2"]:
                script.append("Set-NetIPInterface -InterfaceAlias $wan2 -AddressFamily IPv4 -AutomaticMetric Enabled -ErrorAction Stop")
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
            "WAN primaria: " + p["wan1"] + "\n"
            "WAN secondaria: " + (p["wan2"] or "nessuna") + "\n"
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
