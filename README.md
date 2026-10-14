# WinNAT UI

Applicazione desktop per Windows 10/11 dedicata alla diagnostica e gestione di **WinNAT**, interfacce LAN/WAN e condivisione Internet (ICS).

## Funzioni
- Rilevamento di schede di rete, indirizzi IPv4, gateway, IP forwarding e default route.
- Riepilogo delle regole WinNAT, sessioni NAT e stato del servizio SharedAccess.
- Identificazione *indicativa* della WAN tramite la default route e della LAN tramite la selezione manuale.
- Creazione e rimozione di NAT con avvisi sui conflitti; un solo prefisso interno WinNAT è supportato ufficialmente.
- Setup guidato LAN Ethernet -> Internet (IP LAN, prefisso, forwarding, WinNAT) con rete predefinita `192.168.1.0/24` e IP PC `192.168.1.254`.\n- Rimozione guidata del setup creato dall'app, mantenendo gli IP preesistenti.
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

## Identità e attendibilità dell'eseguibile
Windows mostra ProductName **WinNAT UI**, CompanyName **Matteo Cannizzo**, FileDescription e FileVersion **1.1.0.0** nelle proprietà dell'eseguibile. Questi campi sono dichiarazioni testuali del progetto, **non** attestano l'identità dell'editore. Un programma compilato da GitHub Actions senza certificato resta **non firmato** e Windows SmartScreen potrebbe avvisare l'utente. Per apparire come editore verificato serve un certificato di firma codice appropriato, mantenuto nei secret della CI o tramite servizio di signing, e una firma Authenticode verificabile con `Get-AuthenticodeSignature`. Nessun certificato o approvazione Microsoft è implicito.

## Rimozione setup
La funzione **Rimuovi setup gestito** è disponibile solo se il wizard ha registrato il proprio stato. Rimuove la regola `WinNAT-UI` dopo aver verificato nome e prefisso, e rimuove l'IP LAN soltanto se il wizard lo aveva aggiunto. Non disabilita genericamente l'IP forwarding, né rimuove NAT/ICS altrui. Il backup JSON è diagnostico, non un rollback automatico.

## Modifiche pendenti e commit (v1.2.0)
Le azioni di creazione, eliminazione NAT, configurazione iniziale e rimozione del setup **non vengono applicate al click del relativo comando**: sono registrate nella scheda **Modifiche pendenti**. Da qui è possibile scartarle oppure eseguire **Applica (Commit)** dopo un riepilogo e una conferma. Per ridurre operazioni parziali, il prototipo permette una modifica per commit. Prima del commit rileva nuovamente lo stato e salva un backup diagnostico. Non esiste ancora un rollback transazionale automatico.

## Microsoft Defender
Un utilizzatore ha segnalato il rilevamento `Trojan:Win32/Bearfoos.B!ml` su una build precedente. Il rilevamento **non va ignorato** e non possiamo certificare che sia un falso positivo. Non ripristinare dalla quarantena e non aggiungere esclusioni antivirus. Conservare l'ID del rilevamento, controllare la cronologia di protezione, verificare il codice sorgente e il processo di build e inviare il file a Microsoft per analisi qualora sia stato verificato come legittimo. Le nuove build usano distribuzione `--onedir` e richiedono uno scan Microsoft Defender prima dell'upload; questo non costituisce garanzia di assenza di malware. L'eseguibile rimane non firmato digitalmente.

## Esecuzione verificabile (plaintext)
Dal commit di ottobre 2026, il backend esegue PowerShell attraverso `-Command` con script testuale leggibile nel sorgente `network.py`; non utilizza più `-EncodedCommand`, Base64 o finestre PowerShell nascoste. È possibile eseguire direttamente `py -3 app.py` dal codice sorgente senza usare il wrapper PyInstaller. La distribuzione usa `--onedir --noupx`, per evitare la compressione UPX e consentire ispezione separata dei componenti. L'EXE compilato continua comunque a includere il bootloader PyInstaller e non può essere considerato completamente plaintext.

La documentazione pubblica Microsoft del rilevamento Bearfoos non pubblica pattern tecnici sufficienti per stabilire la causa esatta. Non assumere che l'encoding fosse la ragione dell'avviso né che la sua rimozione garantisca assenza di segnalazioni. Prima della distribuzione esaminare la segnalazione originale, SHA256, esito Defender e, se necessario, inviare il campione tramite il portale ufficiale Microsoft.

## Gate antivirus obbligatorio (CI)
Ogni push su `main` e ogni avvio manuale del workflow compila il programma e richiede la scansione della directory di output con Microsoft Defender. La CI controlla che il motore antivirus risulti disponibile, esegue `Start-MpScan`, consulta le rilevazioni riferite alla build e verifica che l'EXE non sia sparito. In caso di rilevamento o errore di scansione, la build fallisce e **l'artefatto non viene pubblicato**. Non viene più eseguito `Update-MpSignature`: il runner mostra versione e data delle firme già presenti. Lo scan non equivale a una prova che il programma sia innocuo e non sostituisce test locali con firme aggiornate. Un rilevamento non deve essere aggirato cambiando codice per eludere firme; bisogna individuare la componente segnalata, verificare il sorgente e chiedere una revisione Microsoft dove appropriato.

## Provenienza, autore e firma digitale
Il progetto pubblica versione, autore e descrizione nelle risorse Windows dell'eseguibile. Questi metadati NON attestano l'identità dell'autore. La pipeline verifica con `Get-AuthenticodeSignature` se l'eseguibile è firmato, e non lo dichiara firmato in assenza di una firma valida.

### Politica di distribuzione
- Il progetto è attualmente privato: nessuna dichiarazione di eleggibilità per un certificato open source.
- Una build viene pubblicata come artefatto soltanto quando supera compilazione, controlli metadati e verifica Defender.
- Sono pubblicati SHA256 e versione delle definizioni antivirus adoperate.
- Non vengono applicate eccezioni o esclusioni antivirus.
- Il certificato di code signing dovrà provenire da una CA riconosciuta oppure da un servizio di firma ufficiale con identità verificata.
- Il fatto che un binario sia firmato non garantisce che sia privo di vulnerabilità o malware.

### Opzioni di firma esaminate (ottobre 2026)
- **SignPath Foundation**: servizio gratuito per progetti open source pubblici e idonei, con certificato emesso alla Foundation. Il repository privato attuale non soddisfa questo requisito.
- **Microsoft Artifact Signing**: servizio a pagamento con verifica dell'identità.
- **Microsoft Store (MSIX)**: percorso di firma/distribuzione tramite Store con requisiti di pubblicazione.

Fonti ufficiali: https://signpath.org/terms.html ; https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options ; https://azure.microsoft.com/en-us/products/artifact-signing

## Code signing policy

[Code signing policy](CODE_SIGNING_POLICY.md). Free code signing provided by SignPath.io, certificate by SignPath Foundation **only if and after the project is approved**. No signing certificate has been granted yet. Project roles, manual approval, and privacy commitments are described in the policy. The executable is currently unsigned.

To uninstall the portable application, close it and remove the extracted application directory. To remove any networking changes created by the setup wizard, use **Rimuovi setup gestito** before deleting the directory.
