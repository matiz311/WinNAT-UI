# WinNAT UI

Applicazione desktop per Windows 10/11 dedicata alla diagnostica e gestione di **WinNAT**, interfacce LAN/WAN e condivisione Internet (ICS).

## Funzioni
- Rilevamento di schede di rete, indirizzi IPv4, gateway, IP forwarding e default route.
- Riepilogo delle regole WinNAT, sessioni NAT e stato del servizio SharedAccess.
- Identificazione *indicativa* della WAN tramite la default route e della LAN tramite la selezione manuale.
- Creazione e rimozione di NAT con avvisi sui conflitti; un solo prefisso interno WinNAT è supportato ufficialmente.
- Setup guidato LAN Ethernet -> Internet (IP LAN, prefisso, forwarding, WinNAT).
- Esportazione diagnostica JSON e backup di configurazione prima dei cambiamenti.
- Conferme esplicite per ogni intervento potenzialmente distruttivo.

## Avvio
Scarica l'artefatto `WinNAT-UI-Windows` dalla sezione **Actions** della build riuscita, estrai il file ZIP, avvia `WinNAT-UI.exe` come amministratore.

Alternativa per sviluppo:
```powershell
py -3 app.py
```

Richiede Windows con PowerShell 5.1+ e privilegi amministrativi per modificare le impostazioni di rete.

## Build
Workflow GitHub Actions: `.github/workflows/build.yml` produce un file EXE con PyInstaller e lo pubblica come artefatto. Il workflow è avviabile anche manualmente da **Actions -> Build Windows executable -> Run workflow**.

## Attenzione
**Non** è un router hardware, non fornisce DHCP/DNS ai client e non verifica automaticamente la raggiungibilità dei dispositivi esterni. Configura staticamente sul client un IP della subnet LAN, gateway pari all'IP LAN del PC e DNS raggiungibile. Se ICS gestisce già la LAN, evita di sovrapporlo a WinNAT. Il rilevamento WAN/LAN è euristico e richiede conferma.

WinNAT Microsoft è progettato per un singolo prefisso interno: più istanze configurate contemporaneamente non sono una soluzione multipla supportata. Per reti multiple considera routing verso un unico prefisso NAT aggregato oppure una soluzione routing/NAT dedicata. Il programma non elimina automaticamente NAT di Hyper-V, VPN o altre applicazioni.

### Riferimenti
- [Microsoft: Set up a NAT network](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/setup-nat-network)
- [Microsoft: New-NetNat](https://learn.microsoft.com/en-us/powershell/module/netnat/new-netnat)
- [Microsoft: Get-NetNat](https://learn.microsoft.com/en-us/powershell/module/netnat/get-netnat)

## Stato
Versione iniziale, da validare su Windows reale. Prima prova consigliata: diagnostica senza modifiche e successiva configurazione in ambiente di test.
