# WinNAT UI

**Italiano** | [English](README.en.md)

[![Download Windows ZIP](https://img.shields.io/badge/Download-Windows%20ZIP-blue?logo=windows)](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)
[![Latest release](https://img.shields.io/github/v/release/matiz311/WinNAT-UI)](https://github.com/matiz311/WinNAT-UI/releases/latest)
[![Build Windows executable](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml/badge.svg)](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml)

**[Download WinNAT UI for Windows](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)** — scarica lo ZIP della release pubblica, estrai completamente la cartella e avvia `WinNAT-UI.exe`. La release attuale è **non firmata**; la firma tramite SignPath Foundation non è ancora approvata.

- [Release e changelog](https://github.com/matiz311/WinNAT-UI/releases)
- [Informativa privacy](PRIVACY.it.md) ([English](PRIVACY.md))
- [Politica di firma](CODE_SIGNING_POLICY.it.md) ([English](CODE_SIGNING_POLICY.md))
- [Changelog](CHANGELOG.md)
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
Windows mostra ProductName **WinNAT UI**, CompanyName **Matteo Cannizzo**, FileDescription e FileVersion (uguale alla versione in `version.py`) nelle proprietà dell'eseguibile. Questi campi sono dichiarazioni testuali del progetto, **non** attestano l'identità dell'editore. Un programma compilato da GitHub Actions senza certificato resta **non firmato** e Windows SmartScreen potrebbe avvisare l'utente. Per apparire come editore verificato serve un certificato di firma codice appropriato, mantenuto nei secret della CI o tramite servizio di signing, e una firma Authenticode verificabile con `Get-AuthenticodeSignature`. Nessun certificato o approvazione Microsoft è implicito.

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

## Interfaccia v1.3.0
- **Dashboard**: panoramica della configurazione reale, indipendente dalle sessioni NAT.
- **NAT**: mostra regole applicate e modifiche candidate nello stesso elenco; le righe indicano se una regola sarà aggiunta o eliminata.
- **Rete**: prepara configurazione o rimozione del setup guidato.
- **Modifiche**: mostra il riepilogo prima del commit; **Scarta** annulla la configurazione candidata.
- **Sessioni**: legge le sessioni con una chiamata indipendente, aggiornandole ogni 60 secondi quando la scheda è aperta; **Aggiorna** forza la lettura.
- Durante le operazioni asincrone viene mostrata una barra di avanzamento. Il processo PowerShell non apre una finestra separata. La barra è indeterminata: mostra attività in corso, non la percentuale completata.

Per prudenza il commit applica **una modifica alla volta**, anche se è possibile prepararne diverse. Non esiste un rollback automatico delle modifiche Windows.

## Versione 1.4.0: reset di configurazioni preesistenti
- La raccolta di adattatori, IPv4, route, forwarding e NAT usa thread paralleli; le sessioni restano indipendenti.
- In **Rete > Rimuovi esistente** puoi preparare la rimozione del NAT presente per la subnet selezionata anche se creato esternamente all'app.
- L'IP della scheda LAN viene mantenuto salvo selezione esplicita dell'opzione di rimozione esatta; ICS, DHCP, VPN e configurazioni non corrispondenti non vengono rimossi.
- Controlla la configurazione candidata nella tab **Modifiche**, quindi utilizza **Commit**. Dopo la rimozione puoi preparare un nuovo setup dalla stessa schermata.
- La modifica delle interfacce può interrompere la connettività: usare una sessione locale, non una connessione remota dipendente dal NAT da rimuovere.

## Versione 1.6.0 — Configurazione completa da PC vergine

**Rete → Configura** segue la guida operativa «NAT e Routing IPv4 su Windows 11»: scegli LAN, WAN primaria ed eventuale WAN secondaria, subnet LAN, IP gateway, nome NAT e metriche. Il profilo propone Ethernet / USB-C / Wi-Fi, LAN `10.10.10.0/24`, gateway `10.10.10.1`, NAT `NAT-Firewall` e metriche 10/50. Tutti i parametri sono modificabili.

- **Configura:** disabilita DHCP sulla LAN, elimina indirizzi e route IPv4 della LAN, assegna l'IP statico senza default gateway, imposta `IPEnableRouter=1`, abilita il forwarding sulle interfacce selezionate, applica le metriche WAN e crea il NAT. Le WAN devono già essere operative con gateway verso Internet; non vengono cambiati indirizzo, DHCP e DNS delle WAN.
- **Disabilita:** elimina **tutti gli oggetti WinNAT**, anche quelli creati manualmente o da altre applicazioni; disabilita il forwarding sulle interfacce LAN/WAN selezionate e imposta `IPEnableRouter=0`. Conserva indirizzamento LAN e metriche WAN.
- **Ripristina:** oltre alla disabilitazione, rimuove tutti gli IPv4 e le route della LAN selezionata, ripristina il DHCP sulla LAN e le metriche automatiche delle WAN selezionate. Non ripristina la configurazione originale preesistente né elimina le configurazioni WAN.
- **Candidate → Commit:** mostra l'elenco dettagliato delle operazioni e richiede conferma. Raccoglie nuovamente la configurazione prima di applicare; se è cambiata, blocca il commit. Salva uno snapshot JSON prima delle modifiche, **non** un rollback automatico.
- **Riavvio:** dopo la modifica di `IPEnableRouter` è raccomandato riavviare Windows prima di validare il routing.

**Avviso:** la rimozione di tutti gli oggetti WinNAT può interrompere Hyper-V, WSL2 e ambienti container. Anche il reset di IPv4 o delle route può far perdere una connessione di amministrazione remota. Usare una console locale, controllare tutte le interfacce selezionate e verificare l'anteprima prima del Commit. Un commit fallito può aver già applicato alcune modifiche.

**Test suggerito:** apri l'app con privilegi amministrativi → configura LAN/WAN → controlla Modifiche → Commit → riavvia se richiesto → verifica indirizzamento, default route, NAT e sessioni → Disabilita / Ripristina con un nuovo Commit.

I test automatici di pianificazione sono in `test_network_guide.py`.

## Correzione v1.7.0 — DHCP PersistentStore e IP statico
In alcune configurazioni Windows 11, `New-NetIPAddress` fallisce con `Inconsistent parameters PolicyStore PersistentStore and Dhcp Enabled`, anche dopo la disabilitazione DHCP con `Set-NetIPInterface`. Il passaggio LAN a IPv4 statico utilizza ora `netsh interface ipv4 set address source=static ... gateway=none store=persistent`, con verifica dell'IP e dello stato DHCP dopo l'operazione. Il ripristino a DHCP utilizza analogamente `source=dhcp`.

La configurazione candidata e il Commit restano invariati. Se un Commit fallisce, la GUI scarta il candidato non più affidabile e aggiorna lo stato reale di Windows: **controlla prima di riprovare**, perché alcune operazioni precedenti all'errore possono essere state eseguite.

Il comando `netsh` è documentato da Microsoft: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-interface.

## Interfaccia v1.7.1 — redesign UX
- **Navigazione laterale** con sezioni Panoramica, Regole NAT, Gateway, Modifiche, Sessioni (Ctrl+1…6) e indicatore permanente *Amministratore / Sola lettura*.
- **Panoramica** con verdetto unico sullo stato del gateway, riquadri WAN/WinNAT/Routing/ICS con badge testuali (mai solo colore), tabelle interfacce e default route; il testo diagnostico grezzo resta in *Dettagli tecnici*.
- **Gateway**: schema topologico LAN → PC → WAN → Internet aggiornato in tempo reale, campi raggruppati in 3 passi con validazione inline e anteprima numerata di cosa farà il Commit; il pulsante si abilita solo con dati validi.
- **Barra modifiche** fissa in basso: unico punto per Scarta / Rivedi / Applica; il commit richiede una conferma esplicita della possibile interruzione di rete.
- Tema chiaro/scuro che segue Windows, testo nitido su schermi high-DPI, notifiche non bloccanti al posto dei popup informativi. Nessuna nuova dipendenza: solo Tkinter/ttk (`ui_theme.py`).


## Versione 1.9.1 — WAN dinamiche e subnet LAN automatica
- **Gateway → Configura** parte con una sola WAN; **+ Aggiungi WAN** ne aggiunge altre (fino al numero di interfacce del PC), con priorità riordinabile e metriche crescenti.
- Scegliendo la LAN, l'IPv4 già presente sulla scheda viene riutilizzato come IP statico senza gateway e la sua subnet diventa quella del NAT; senza un IPv4 utilizzabile si usa `10.10.10.0/24` con IP `10.10.10.1`. I valori restano modificabili.
- La subnet LAN non può sovrapporsi a quella di una WAN.
