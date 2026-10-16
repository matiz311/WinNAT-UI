<img src="assets/winnat-ui-256.png" alt="" width="96" align="right">

# WinNAT UI

**Italiano** | [English](README.en.md)

[![Download Windows ZIP](https://img.shields.io/badge/Download-Windows%20ZIP-blue?logo=windows)](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)
[![Latest release](https://img.shields.io/github/v/release/matiz311/WinNAT-UI)](https://github.com/matiz311/WinNAT-UI/releases/latest)
[![Build Windows executable](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml/badge.svg)](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml)

**[Download WinNAT UI for Windows](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)** — scarica lo ZIP della release pubblica, estrai completamente la cartella e avvia `WinNAT-UI.exe`. La release corrente è **v1.14.0**, **non firmata**; la firma tramite SignPath Foundation non è ancora approvata.

- [Release e changelog](https://github.com/matiz311/WinNAT-UI/releases)
- [Informativa privacy](PRIVACY.it.md) ([English](PRIVACY.md))
- [Politica di firma](CODE_SIGNING_POLICY.it.md) ([English](CODE_SIGNING_POLICY.md))
- [Changelog](CHANGELOG.md)
- Aggiornamento integrato: in **Informazioni → Controlla aggiornamenti**, oppure all'avvio quando è disponibile una release stabile più recente; scarica da GitHub e verifica SHA256 prima della sostituzione dei file al riavvio.
- [Politica di versioning e build](VERSIONING_POLICY.md)
- [Licenza MIT](LICENSE)


Applicazione desktop per Windows 10/11 dedicata alla diagnostica e gestione di **WinNAT**, interfacce LAN/WAN e condivisione Internet (ICS).

## Funzioni
- Rilevamento di schede di rete, indirizzi IPv4, gateway, IP forwarding e default route.
- Riepilogo delle regole WinNAT, sessioni NAT e stato del servizio SharedAccess.
- Identificazione *indicativa* della WAN tramite la default route e della LAN tramite la selezione manuale.
- Creazione e rimozione di NAT con avvisi sui conflitti; un solo prefisso interno WinNAT è supportato ufficialmente.
- Setup guidato LAN Ethernet -> Internet (IP LAN, prefisso, forwarding, WinNAT) con rete predefinita `10.10.10.0/24` e IP PC `10.10.10.1`.
- Rimozione guidata del setup creato dall'app, mantenendo gli IP preesistenti.
- Esportazione diagnostica JSON e backup di configurazione prima dei cambiamenti.
- Conferme esplicite per ogni intervento potenzialmente distruttivo.

## Avvio
Scarica il file ZIP dalla [pagina Download](https://github.com/matiz311/WinNAT-UI/releases/latest), estrai tutti i file e avvia `WinNAT-UI.exe` come amministratore. In alternativa gli artifact delle build sono disponibili dalla sezione Actions.

Alternativa per sviluppo:
```powershell
py -3 app.py
```

Richiede Windows con PowerShell 5.1+ e privilegi amministrativi per modificare le impostazioni di rete.


## Struttura del repository
Il codice è organizzato per funzione, senza affollare la radice del progetto:

- `app.py` — punto di avvio dell'app, compatibile con `py -3 app.py` e con PyInstaller.
- `version.py` e `version_info.txt` — numerazione funzionale e metadati Windows richiesti dalla procedura di rilascio.
- `winnat_ui/` — moduli dell'app (rete, WinNAT, UI, updater e segnalazione errori).
- `tests/` — test Python eseguiti in CI con `python -m unittest discover -s tests -t . -v`.
- `tools/` — script di diagnostica e manutenzione; `assets/` — icone e risorse grafiche.
- `services/` — servizi esterni; `.github/workflows/` — automazioni GitHub Actions.

I file `.md`, `LICENSE` e `bug-service.json` restano in radice per preservare la documentazione, le policy e l'URL usato dal client.

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
**Versione pubblicata: v1.14.0 (16 ottobre 2026).** Build Windows e test CI superati; restano necessari test operativi su un computer Windows reale, soprattutto per configurazioni di rete e updater. Prima prova consigliata: diagnostica in sola lettura in ambiente di test.

## Identità e attendibilità dell'eseguibile
Windows mostra ProductName **WinNAT UI**, CompanyName **Matteo Cannizzo**, FileDescription e FileVersion (uguale alla versione in `version.py`) nelle proprietà dell'eseguibile. Questi campi sono dichiarazioni testuali del progetto, **non** attestano l'identità dell'editore. Un programma compilato da GitHub Actions senza certificato resta **non firmato** e Windows SmartScreen potrebbe avvisare l'utente. Per apparire come editore verificato serve un certificato di firma codice appropriato, mantenuto nei secret della CI o tramite servizio di signing, e una firma Authenticode verificabile con `Get-AuthenticodeSignature`. Nessun certificato o approvazione Microsoft è implicito.

## Rimozione setup
La funzione **Rimuovi setup gestito** è disponibile solo se il wizard ha registrato il proprio stato. Rimuove la regola `WinNAT-UI` dopo aver verificato nome e prefisso, e rimuove l'IP LAN soltanto se il wizard lo aveva aggiunto. Non disabilita genericamente l'IP forwarding, né rimuove NAT/ICS altrui. Il backup JSON è diagnostico, non un rollback automatico.

## Modifiche pendenti e commit
Le azioni di creazione, eliminazione NAT, configurazione iniziale e rimozione del setup **non vengono applicate al click del relativo comando**: sono registrate nella scheda **Modifiche pendenti**. Da qui è possibile scartarle oppure eseguire **Applica (Commit)** dopo un riepilogo e una conferma. Viene applicata una modifica candidata per commit.

Per **Configura gateway**, il candidato rappresenta lo **stato desiderato**: immediatamente prima del Commit l'app rilegge Windows, calcola il delta e applica soltanto ciò che manca. Un retry dopo un errore non ripete quindi IP, forwarding, metriche o NAT già convergenti. Dopo le scritture viene eseguita una nuova lettura per verificare che il delta sia vuoto. Le operazioni distruttive **Disabilita/Ripristina** mantengono invece il controllo stretto dell'impronta e si bloccano se la configurazione rilevante è cambiata dall'anteprima.

L'app salva checkpoint locali `candidate-commit`, `pre-commit`, `post-commit` e, se necessario, `post-rollback` in `%LOCALAPPDATA%\WinNAT-UI\commit-states`. Il rollback resta compensativo e best-effort: Windows non offre una transazione atomica della configurazione di rete.

## Microsoft Defender
Un utilizzatore ha segnalato il rilevamento `Trojan:Win32/Bearfoos.B!ml` su una build precedente. Il rilevamento **non va ignorato** e non possiamo certificare che sia un falso positivo. Non ripristinare dalla quarantena e non aggiungere esclusioni antivirus. Conservare l'ID del rilevamento, controllare la cronologia di protezione, verificare il codice sorgente e il processo di build e inviare il file a Microsoft per analisi qualora sia stato verificato come legittimo. Le nuove build usano distribuzione `--onedir` e richiedono uno scan Microsoft Defender prima dell'upload; questo non costituisce garanzia di assenza di malware. L'eseguibile rimane non firmato digitalmente.

## Esecuzione verificabile (plaintext)
Dal commit di ottobre 2026, il backend esegue PowerShell attraverso `-Command` con script testuale leggibile nel sorgente [`winnat_ui/network.py`](winnat_ui/network.py); non utilizza più `-EncodedCommand`, Base64 o finestre PowerShell nascoste. È possibile eseguire direttamente `py -3 app.py` dal codice sorgente senza usare il wrapper PyInstaller. La distribuzione usa `--onedir --noupx`, per evitare la compressione UPX e consentire ispezione separata dei componenti. L'EXE compilato continua comunque a includere il bootloader PyInstaller e non può essere considerato completamente plaintext.

La documentazione pubblica Microsoft del rilevamento Bearfoos non pubblica pattern tecnici sufficienti per stabilire la causa esatta. Non assumere che l'encoding fosse la ragione dell'avviso né che la sua rimozione garantisca assenza di segnalazioni. Prima della distribuzione esaminare la segnalazione originale, SHA256, esito Defender e, se necessario, inviare il campione tramite il portale ufficiale Microsoft.

## Gate antivirus obbligatorio (CI)
Ogni push su `main` e ogni avvio manuale del workflow compila il programma e richiede la scansione della directory di output con Microsoft Defender. La CI controlla che il motore antivirus risulti disponibile, esegue `Start-MpScan`, consulta le rilevazioni riferite alla build e verifica che l'EXE non sia sparito. In caso di rilevamento o errore di scansione, la build fallisce e **l'artefatto non viene pubblicato**. Non viene più eseguito `Update-MpSignature`: il runner mostra versione e data delle firme già presenti. Lo scan non equivale a una prova che il programma sia innocuo e non sostituisce test locali con firme aggiornate. Un rilevamento non deve essere aggirato cambiando codice per eludere firme; bisogna individuare la componente segnalata, verificare il sorgente e chiedere una revisione Microsoft dove appropriato.

## Provenienza, autore e firma digitale
Il progetto pubblica versione, autore e descrizione nelle risorse Windows dell'eseguibile. Questi metadati NON attestano l'identità dell'autore. La pipeline verifica con `Get-AuthenticodeSignature` se l'eseguibile è firmato, e non lo dichiara firmato in assenza di una firma valida.

### Politica di distribuzione
- Il repository è pubblico, ma la candidatura e la verifica SignPath Foundation non sono ancora concluse.
- Una build viene pubblicata come artefatto soltanto quando supera compilazione, controlli metadati e verifica Defender.
- Sono pubblicati SHA256 e versione delle definizioni antivirus adoperate.
- Non vengono applicate eccezioni o esclusioni antivirus.
- Il certificato di code signing dovrà provenire da una CA riconosciuta oppure da un servizio di firma ufficiale con identità verificata.
- Il fatto che un binario sia firmato non garantisce che sia privo di vulnerabilità o malware.

### Opzioni di firma esaminate (ottobre 2026)
- **SignPath Foundation**: servizio gratuito per progetti open source pubblici e idonei, con certificato emesso alla Foundation. Il repository è ora pubblico; l'idoneità è comunque soggetta alla valutazione di SignPath.
- **Microsoft Artifact Signing**: servizio a pagamento con verifica dell'identità.
- **Microsoft Store (MSIX)**: percorso di firma/distribuzione tramite Store con requisiti di pubblicazione.

Fonti ufficiali: https://signpath.org/terms.html ; https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options ; https://azure.microsoft.com/en-us/products/artifact-signing

## Politica di firma digitale

Consulta la [politica di firma](CODE_SIGNING_POLICY.it.md) ([English](CODE_SIGNING_POLICY.md)). L'attribuzione «Free code signing provided by SignPath.io, certificate by SignPath Foundation» sarà applicabile solo in caso di approvazione; l'eseguibile attuale è ancora non firmato.

Per disinstallare il programma portatile, chiudilo e rimuovi la cartella estratta. Prima di farlo, se hai configurato la rete con il wizard, utilizza **Rimuovi setup gestito**.

## Evoluzione delle funzionalità — release pubblicate

Le funzioni presenti nella **v1.14.0** derivano dai rilasci elencati sotto. Il 16 ottobre 2026 le 28 release precedenti sono state ripubblicate con numerazione coerente, eseguibili ricompilati e tag verificati. I numeri riportati qui sono **quelli effettivamente disponibili** nella [pagina Releases](https://github.com/matiz311/WinNAT-UI/releases); per il dettaglio di ogni versione consulta il [Changelog](CHANGELOG.md) e le [Note di rilascio](RELEASE_NOTES.it.md).

- **v1.2.0–v1.4.0:** distribuzione iniziale, inventario di rete, dashboard, modifiche candidate, Commit e rimozione guidata di configurazioni NAT.
- **v1.5.0–v1.5.2:** configurazione completa del gateway Windows, più correzioni per DHCP, PersistentStore e IPv4 LAN statico.
- **v1.6.0–v1.6.4:** nuova interfaccia laterale, tema chiaro/scuro e diagnostica PowerShell più completa.
- **v1.7.0–v1.9.0:** diagnostica di compatibilità, rollback compensativo, supporto alle WAN dinamiche e rilevamento della subnet LAN.
- **v1.10.0–v1.11.2:** updater con verifica SHA-256, segnalazione di bug e relativo gateway, diagnostica e tracciamento delle Issue.
- **v1.12.0–v1.12.5:** Commit idempotente con checkpoint, evoluzione del backend NAT e gestione più prudente di indirizzi e subnet LAN.
- **v1.13.0 e v1.13.0.1:** aggregazione delle subnet per i percorsi avanzati del gateway e HOTFIX che mantiene separata l'azione semplice «Aggiungi NAT».
- **v1.14.0:** distribuzione e verifica del gateway anonimo per le segnalazioni e miglioramento della diagnostica dell'updater.

**Nota operativa:** le operazioni di modifica della rete non sono transazioni atomiche Windows. Verifica sempre anteprima, backup e accesso locale; l'updater automatico deve ancora essere validato su una macchina Windows reale.
