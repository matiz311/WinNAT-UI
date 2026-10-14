<#
.SYNOPSIS
    WinNAT UI - diagnostica di compatibilita' (SOLA LETTURA).

.DESCRIPTION
    Raccoglie le informazioni di rete necessarie per capire se e come WinNAT UI
    puo' trasformare questo PC in un gateway LAN -> NAT -> WAN.
    Lo script NON modifica alcuna impostazione: usa solo comandi Get-*.

    Produce, nella cartella indicata (default: accanto allo script):
      - WinNAT-Diagnostica-<data>.json  dati completi per gli sviluppatori
      - WinNAT-Diagnostica-<data>.txt   riepilogo leggibile con verdetto

    Privacy: non vengono raccolti nome del PC, nome utente, indirizzi MAC,
    SSID Wi-Fi o IP pubblici. Restano gli indirizzi IPv4 privati e i nomi delle
    schede di rete: controlla il file prima di condividerlo pubblicamente.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File .\WinNAT-Diagnostica.ps1
    (consigliato da PowerShell avviato come amministratore: alcune voci
     come le funzionalita' Hyper-V richiedono privilegi elevati)
#>
[CmdletBinding()]
param([string]$OutputFolder = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
$ScriptVersion = '1.0'
$result = [ordered]@{ meta = [ordered]@{}; errors = [ordered]@{} }

function Grab([string]$key, [scriptblock]$block) {
    try { $result[$key] = @(& $block) }
    catch { $result[$key] = @(); $result.errors[$key] = $_.Exception.Message }
}

function IsPrivate([string]$ip) {
    if ($ip -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.|127\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)') { return $true }
    return $false
}

# ------------------------------------------------------------ sistema ---
$os = Get-CimInstance Win32_OperatingSystem
$identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$result.meta = [ordered]@{
    scriptVersion  = $ScriptVersion
    collectedAt    = (Get-Date).ToString('o')
    os             = $os.Caption
    version        = $os.Version
    build          = $os.BuildNumber
    ubr            = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue).UBR
    displayVersion = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue).DisplayVersion
    architecture   = $os.OSArchitecture
    uiCulture      = (Get-UICulture).Name
    psVersion      = $PSVersionTable.PSVersion.ToString()
    isAdmin        = $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    virtualMachine = (Get-CimInstance Win32_ComputerSystem).Model
}

Grab 'commands' {
    foreach ($c in 'Get-NetNat','New-NetNat','Get-NetNatSession','Get-NetIPInterface','Get-VMSwitch','Get-HnsNetwork') {
        [ordered]@{ name = $c; available = [bool](Get-Command $c -ErrorAction SilentlyContinue) }
    }
}

# ------------------------------------------------------------- schede ---
Grab 'adapters' {
    Get-NetAdapter -IncludeHidden | ForEach-Object {
        [ordered]@{
            Name = $_.Name; InterfaceIndex = $_.ifIndex; InterfaceDescription = $_.InterfaceDescription
            Status = [string]$_.Status; MediaType = $_.MediaType; PhysicalMediaType = $_.PhysicalMediaType
            NdisPhysicalMedium = [string]$_.NdisPhysicalMedium; Virtual = $_.Virtual
            HardwareInterface = $_.HardwareInterface; ConnectorPresent = $_.ConnectorPresent
            Hidden = $_.Hidden; LinkSpeed = $_.LinkSpeed; DriverProvider = $_.DriverProvider
            ComponentID = $_.ComponentID
        }
    }
}
Grab 'interfaces' {
    Get-NetIPInterface -AddressFamily IPv4 | Select-Object InterfaceAlias, InterfaceIndex, Forwarding, Dhcp,
        AutomaticMetric, InterfaceMetric, ConnectionState, NlMtu, @{n='Store';e={[string]$_.Store}}
}
Grab 'ips' {
    Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, InterfaceIndex, IPAddress, PrefixLength,
        @{n='PrefixOrigin';e={[string]$_.PrefixOrigin}}, @{n='SuffixOrigin';e={[string]$_.SuffixOrigin}},
        @{n='AddressState';e={[string]$_.AddressState}}, @{n='Store';e={[string]$_.Store}} |
        Where-Object { IsPrivate $_.IPAddress }
}
Grab 'publicAddressCount' {
    @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { -not (IsPrivate $_.IPAddress) }).Count
}
Grab 'routes' {
    Get-NetRoute -AddressFamily IPv4 | Where-Object { $_.DestinationPrefix -notmatch '^(224\.|255\.255\.255\.255)' } |
        Select-Object InterfaceAlias, InterfaceIndex, DestinationPrefix, NextHop, RouteMetric, InterfaceMetric,
        @{n='Protocol';e={[string]$_.Protocol}}, @{n='Store';e={[string]$_.Store}}
}
Grab 'dns' {
    Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object { $_.ServerAddresses } |
        Select-Object InterfaceAlias, @{n='Servers';e={ @($_.ServerAddresses | ForEach-Object { if (IsPrivate $_) { $_ } else { 'pubblico' } }) }}
}
Grab 'connectionProfiles' {
    Get-NetConnectionProfile | Select-Object InterfaceAlias, @{n='NetworkCategory';e={[string]$_.NetworkCategory}},
        @{n='IPv4Connectivity';e={[string]$_.IPv4Connectivity}}
}

# --------------------------------------------------- NAT, ICS, routing ---
Grab 'nats' {
    Get-NetNat | Select-Object Name, InternalIPInterfaceAddressPrefix, ExternalIPInterfaceAddressPrefix, Active, Store
}
Grab 'natStaticMappings' { Get-NetNatStaticMapping | Select-Object NatName, Protocol, ExternalPort, InternalIPAddress, InternalPort }
Grab 'natSessionCount' { @(Get-NetNatSession).Count }
Grab 'ipEnableRouter' {
    (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name IPEnableRouter -ErrorAction SilentlyContinue).IPEnableRouter
}
Grab 'services' {
    foreach ($s in 'SharedAccess','RemoteAccess','hns','vmms','WinNat','iphlpsvc') {
        $svc = Get-Service $s -ErrorAction SilentlyContinue
        if ($svc) { [ordered]@{ Name = $s; Status = [string]$svc.Status; StartType = [string]$svc.StartType } }
        else { [ordered]@{ Name = $s; Status = 'NonPresente'; StartType = '' } }
    }
}
Grab 'icsConnections' {
    $m = New-Object -ComObject HNetCfg.HNetShare
    foreach ($c in $m.EnumEveryConnection()) {
        $p = $m.NetConnectionProps($c)
        $cfg = $m.INetSharingConfigurationForINetConnection($c)
        [ordered]@{ Name = $p.Name; SharingEnabled = [bool]$cfg.SharingEnabled
                    SharingType = $(if ($cfg.SharingEnabled) { [int]$cfg.SharingConnectionType } else { $null }) }
    }
}

# ----------------------------------------------- virtualizzazione / altro ---
Grab 'vmSwitches' {
    if (Get-Command Get-VMSwitch -ErrorAction SilentlyContinue) {
        Get-VMSwitch | Select-Object Name, @{n='SwitchType';e={[string]$_.SwitchType}}, NetAdapterInterfaceDescription
    }
}
Grab 'firewallProfiles' { Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction }
Grab 'winnatUiState' {
    $f = Join-Path $env:LOCALAPPDATA 'WinNAT-UI'
    if (Test-Path $f) { [ordered]@{ folder = $true; backups = @(Get-ChildItem (Join-Path $f 'backups') -ErrorAction SilentlyContinue).Count } }
    else { [ordered]@{ folder = $false; backups = 0 } }
}

# ------------------------------------------------------------- analisi ---
$up = @($result.adapters | Where-Object { $_.Status -eq 'Up' })
$defaults = @($result.routes | Where-Object { $_.DestinationPrefix -eq '0.0.0.0/0' })
$wanAliases = @($defaults | ForEach-Object { $_.InterfaceAlias } | Select-Object -Unique)
$ifaceAliases = @($result.interfaces | ForEach-Object { $_.InterfaceAlias })
$lanCandidates = @($result.adapters | Where-Object {
    $_.Name -notin $wanAliases -and $_.Name -in $ifaceAliases -and $_.Name -notmatch '^vEthernet' -and
    $_.InterfaceDescription -notmatch 'Bluetooth|WAN Miniport|Teredo|Kernel Debug|TAP-|WireGuard|Hyper-V Virtual'
})
$loopback = @($result.adapters | Where-Object { $_.InterfaceDescription -match 'KM-TEST|Loopback' })
$virtualSw = @($result.adapters | Where-Object { $_.Name -match '^vEthernet' -or $_.InterfaceDescription -match 'Hyper-V Virtual' })
$icsOn = @($result.icsConnections | Where-Object { $_.SharingEnabled })

$checks = New-Object System.Collections.ArrayList
function Check($level, $text) { [void]$checks.Add([ordered]@{ level = $level; text = $text }) }

if (-not $result.meta.isAdmin) { Check 'AVVISO' 'Script non eseguito come amministratore: alcune informazioni (Hyper-V, sessioni NAT) potrebbero mancare.' }
if (-not ($result.commands | Where-Object { $_.name -eq 'New-NetNat' -and $_.available })) {
    Check 'BLOCCO' 'Il cmdlet New-NetNat non e'' disponibile: WinNAT non e'' utilizzabile su questa edizione/versione di Windows.'
} else { Check 'OK' 'Modulo NetNat disponibile.' }
if ($wanAliases.Count -eq 0) { Check 'BLOCCO' 'Nessuna default route IPv4: serve una WAN gia'' connessa a Internet.' }
else { Check 'OK' ('WAN candidate (con default route): ' + ($wanAliases -join ', ')) }
if ($lanCandidates.Count -eq 0) {
    Check 'BLOCCO' 'Nessuna scheda utilizzabile come LAN distinta dalla WAN. Serve una seconda scheda (USB-Ethernet, loopback KM-TEST o scheda virtuale) per i test.'
} else {
    Check 'OK' ('LAN candidate: ' + (($lanCandidates | ForEach-Object { $_.Name + ' [' + $_.Status + ']' }) -join ', '))
    if (-not ($lanCandidates | Where-Object { $_.Status -eq 'Up' })) {
        Check 'AVVISO' 'Le LAN candidate non sono connesse (Status diverso da Up): Windows puo'' rifiutare IP/route finche'' il link e'' assente.'
    }
}
if ($loopback.Count) { Check 'INFO' ('Scheda loopback presente: ' + (($loopback | ForEach-Object { $_.Name }) -join ', ') + '. Utile per test senza seconda scheda fisica (nessun client reale raggiungibile).') }
if (@($result.nats).Count -gt 1) { Check 'AVVISO' 'Piu'' oggetti WinNAT presenti: Windows supporta ufficialmente un solo prefisso interno.' }
elseif (@($result.nats).Count -eq 1) { Check 'INFO' ('WinNAT esistente: ' + $result.nats[0].Name + ' ' + $result.nats[0].InternalIPInterfaceAddressPrefix + '. Il profilo Configura richiede prima Ripristina.') }
if ($icsOn.Count) { Check 'AVVISO' ('Condivisione Internet (ICS) attiva su: ' + (($icsOn | ForEach-Object { $_.Name }) -join ', ') + '. Va disattivata prima di usare WinNAT.') }
if ($virtualSw.Count) { Check 'INFO' ('Switch virtuali Hyper-V/WSL/Docker presenti: ' + (($virtualSw | ForEach-Object { $_.Name }) -join ', ') + '. Disabilita/Ripristina eliminano TUTTI i WinNAT e possono interrompere questi ambienti.') }
if ($result.ipEnableRouter -eq 1) { Check 'INFO' 'IPEnableRouter = 1 (routing IPv4 globale gia'' abilitato).' }
$dhcpLan = @($result.interfaces | Where-Object { $_.InterfaceAlias -in @($lanCandidates | ForEach-Object { $_.Name }) -and [string]$_.Dhcp -eq 'Enabled' })
if ($dhcpLan.Count) { Check 'INFO' ('LAN candidate con DHCP attivo (verra'' convertito in IP statico tramite netsh): ' + (($dhcpLan | ForEach-Object { $_.InterfaceAlias }) -join ', ')) }

$blocking = @($checks | Where-Object { $_.level -eq 'BLOCCO' }).Count
$verdict = if ($blocking) { 'NON PRONTO: risolvi le voci BLOCCO' } elseif (@($checks | Where-Object { $_.level -eq 'AVVISO' }).Count) { 'PRONTO CON AVVISI' } else { 'PRONTO' }
$result.analysis = [ordered]@{
    verdict = $verdict; checks = $checks; wanCandidates = $wanAliases
    lanCandidates = @($lanCandidates | ForEach-Object { $_.Name }); upAdapters = $up.Count
}

# -------------------------------------------------------------- output ---
if (-not $OutputFolder) { $OutputFolder = (Get-Location).Path }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$json = Join-Path $OutputFolder ("WinNAT-Diagnostica-$stamp.json")
$txt = Join-Path $OutputFolder ("WinNAT-Diagnostica-$stamp.txt")
$result | ConvertTo-Json -Depth 6 | Out-File -FilePath $json -Encoding utf8

$lines = @(
    'WinNAT UI - Diagnostica di compatibilita'' (sola lettura) v' + $ScriptVersion,
    ('Data: ' + $result.meta.collectedAt),
    ('Sistema: ' + $result.meta.os + ' ' + $result.meta.displayVersion + ' build ' + $result.meta.build + '.' + $result.meta.ubr + ' | lingua ' + $result.meta.uiCulture + ' | modello ' + $result.meta.virtualMachine),
    ('Amministratore: ' + $result.meta.isAdmin + ' | PowerShell ' + $result.meta.psVersion),
    '', ('VERDETTO: ' + $verdict), ''
)
$lines += $checks | ForEach-Object { '[' + $_.level + '] ' + $_.text }
$lines += '', 'SCHEDE DI RETE'
$lines += $result.adapters | Sort-Object { $_.Status -ne 'Up' } | ForEach-Object {
    $name = $_.Name
    $ip = (@($result.ips | Where-Object { $_.InterfaceAlias -eq $name } | ForEach-Object { $_.IPAddress + '/' + $_.PrefixLength }) -join ', ')
    $if = $result.interfaces | Where-Object { $_.InterfaceAlias -eq $name } | Select-Object -First 1
    '  {0,-28} {1,-13} {2,-38} IPv4: {3}  DHCP={4} Fwd={5} Metrica={6}' -f $name, $_.Status, $_.InterfaceDescription, ($(if ($ip) { $ip } else { '-' })), $if.Dhcp, $if.Forwarding, $if.InterfaceMetric
}
$lines += '', 'DEFAULT ROUTE'
$lines += $defaults | ForEach-Object { '  {0} via {1}  metrica route {2} + interfaccia {3}' -f $_.InterfaceAlias, $_.NextHop, $_.RouteMetric, $_.InterfaceMetric }
$lines += '', ('WinNAT: ' + @($result.nats).Count + ' | ICS attiva: ' + $icsOn.Count + ' | IPEnableRouter: ' + $result.ipEnableRouter + ' | sessioni NAT: ' + $result.natSessionCount)
if ($result.errors.Count) {
    $lines += '', 'VOCI NON LEGGIBILI'
    $lines += $result.errors.Keys | ForEach-Object { '  ' + $_ + ': ' + $result.errors[$_] }
}
$lines += '', 'Nessuna impostazione e'' stata modificata. File completo: ' + (Split-Path $json -Leaf)
$lines | Out-File -FilePath $txt -Encoding utf8
$lines | ForEach-Object { Write-Host $_ }
Write-Host ''
Write-Host ('Salvato in: ' + $OutputFolder) -ForegroundColor Cyan
