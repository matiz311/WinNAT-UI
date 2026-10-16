<img src="assets/winnat-ui-256.png" alt="" width="96" align="right">

# WinNAT UI

**Italiano** | [English](README.en.md)

[![Download Windows ZIP](https://img.shields.io/badge/Download-Windows%20ZIP-blue?logo=windows)](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)
[![Latest release](https://img.shields.io/github/v/release/matiz311/WinNAT-UI)](https://github.com/matiz311/WinNAT-UI/releases/latest)
[![Build Windows executable](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml/badge.svg)](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml)

**[Download WinNAT UI for Windows](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)** — scarica lo ZIP della release pubblica, estrai completamente la cartella e avvia `WinNAT-UI.exe`. La release corrente è **v1.14.0**, **non firmata**; la firma tramite SignPath Foundation non è ancora approvata.

**Preparazione release:** il codice sorgente della prossima MINOR è identificato come **v1.15.0**. Fino all'approvazione e pubblicazione della nuova GitHub Release, il download ufficiale rimane quello dell'ultima versione effettivamente pubblicata. Il nuovo logo è riservato alla v1.15.0.

- [Release e changelog](https://github.com/matiz311/WinNAT-UI/releases)
- [Note di rilascio per versione (consultabili nel README)](#note-di-rilascio-per-versione)
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

## Gestione IPv4 secondari sulla LAN

Nella scheda **Gateway**, sotto l'indirizzo principale della LAN, è disponibile la tabella
**Indirizzi IPv4 secondari della LAN**. Dopo aver selezionato la scheda LAN puoi:
- aggiungere un indirizzo IPv4 con relativo prefisso CIDR (anche appartenente a un'altra subnet);
- modificare indirizzo e/o prefisso di un IPv4 secondario già presente;
- rimuovere un IPv4 secondario selezionato.

Ogni operazione viene **preparata** nella scheda **Modifiche**: Windows viene modificato
soltanto dopo la conferma **Applica (Commit)**. Il software rilegge la configurazione
subito prima del Commit, ricontrolla scheda, indice, DHCP, duplicati e indirizzi già
presenti, applica solo l'operazione scelta e verifica l'esito. In caso di errore
tenta un rollback limitato agli indirizzi selezionati; non è una transazione atomica.

Gli indirizzi aggiunti sono statici e impostati con `SkipAsSource=True`, per non
essere preferiti da Windows come IP sorgente dei normali collegamenti in uscita.
Sono modificabili e rimovibili dalla tabella solo gli indirizzi che Windows
identifica come secondari con `SkipAsSource=True`. Gli altri IPv4 sono visualizzati,
ma protetti. Il software **non** aggiunge gateway predefiniti, non disabilita DHCP
automaticamente e non elimina l'IP principale. Prima di aggiungere indirizzi
secondari serve un indirizzo LAN principale già configurato staticamente.

**NAT e subnet multiple:** aggiungere un IP secondario non espande automaticamente
il prefisso del WinNAT. Se il nuovo IP appartiene a una subnet differente, il
routing/NAT di quella subnet deve essere valutato separatamente: questa funzione
non modifica, ricrea o moltiplica le regole WinNAT. L'aggiunta o la rimozione
di indirizzi può invece aggiornare automaticamente le route direttamente connesse.
Collaudare il traffico reale
su un host Windows e verificare eventuali conflitti con altre interfacce.

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

## Note di rilascio per versione

Le note di rilascio sono consultabili direttamente qui, senza lasciare la pagina principale. Seleziona una versione per espandere le novità, le correzioni e le limitazioni. Per lo storico tecnico completo consulta il [Changelog](CHANGELOG.md); il documento di riferimento è [RELEASE_NOTES.it.md](RELEASE_NOTES.it.md).

<details>
<summary><strong>1.14.0 — 16 ottobre 2026</strong></summary>

**Tema del rilascio: segnalazione anonima dei problemi e diagnostica degli aggiornamenti.**

### Novità
- Attivato il gateway Cloudflare per inviare segnalazioni di bug senza richiedere un account GitHub all'utente. L'endpoint viene distribuito e verificato tramite GitHub Actions.
- Introdotti controlli di salute del servizio, limitazione della frequenza di invio e convalida dei soli metadati previsti. Il gateway conserva le credenziali GitHub sul server anziché nel client.
- Aggiunto un test end-to-end del servizio che invia una segnalazione sintetica, verifica il rilevamento dei duplicati e chiude la Issue di prova.

### Correzioni e affidabilità
- Gestiti i ritardi di indicizzazione delle Issue GitHub per ridurre la creazione di segnalazioni duplicate.
- Accettate versioni sia a tre componenti (es. `1.14.0`) sia HOTFIX a quattro componenti (es. `1.13.0.1`).
- Il controllo manuale degli aggiornamenti restituisce messaggi più specifici quando i metadati della release non sono validi; il controllo automatico all'avvio resta non bloccante in caso di indisponibilità del servizio.

### Compatibilità e limiti
- Nessuna modifica intenzionale alla logica di NAT e routing rispetto alla `1.13.0.1`.
- Le segnalazioni automatiche inviano soltanto metadati anonimizzati predefiniti: non vengono inoltrati automaticamente configurazioni, comandi, credenziali o output PowerShell grezzi.
- I test CI e del gateway non sostituiscono il collaudo su una macchina Windows reale, in particolare per l'aggiornamento dell'app e la riconfigurazione di rete.

</details>

<details>
<summary><strong>1.13.0.1 — 15 ottobre 2026 — HOTFIX</strong></summary>

**Correzione mirata di “Aggiungi NAT”.** Il comando crea la regola richiesta tramite `New-NetNat` senza ricostruire altri oggetti NAT, espandere prefissi o intervenire sugli indirizzi LAN/WAN. Se nome e prefisso coincidono con una regola esistente, l'operazione non ripete modifiche; se il nome collide con una configurazione diversa, viene segnalato il conflitto. Il rollback resta limitato all'oggetto richiesto. Aggiunto il supporto infrastrutturale al numero di versione HOTFIX a quattro componenti.

</details>

<details>
<summary><strong>1.13.0 — 15 ottobre 2026</strong></summary>

**Aggregazione di subnet LAN in una sola istanza WinNAT.** I percorsi di configurazione gateway possono espandere il prefisso dell'istanza WinNAT per comprendere più subnet, cercando di preservare nome, mapping statici e parametri supportati. Il Commit espone l'impatto della ricreazione dell'istanza e il rollback tenta di ripristinare il prefisso precedente. **Attenzione:** la successiva `1.13.0.1` ha deliberatamente separato il comportamento dell'azione semplice “Aggiungi NAT”, che non effettua più questa espansione.

</details>

<details>
<summary><strong>1.12.5 — 15 ottobre 2026</strong></summary>

**Migliorata la coesistenza di più subnet.** Riutilizzo di un'istanza WinNAT quando il suo prefisso include la LAN richiesta; aggiunta di IPv4 LAN senza sostituire indirizzi preesistenti e conservazione delle route non interessate dall'operazione. Se il prefisso NAT non è sufficiente, il Commit non procede a un reset implicito.

</details>

<details>
<summary><strong>1.12.4 — 15 ottobre 2026</strong></summary>

**Semplificata la creazione NAT.** Rimossi alcuni blocchi preventivi globali sul numero di istanze; rimangono i controlli sui nomi duplicati e la verifica dell'esito PowerShell. Questa versione è storica: consultare la `1.13.0.1` per il comportamento corretto di “Aggiungi NAT”.

</details>

<details>
<summary><strong>1.12.3 — 15 ottobre 2026</strong></summary>

**Correzione packaging Windows.** Incluso esplicitamente il modulo backend NAT/IP nell'eseguibile PyInstaller.

</details>

<details>
<summary><strong>1.12.2 — 15 ottobre 2026</strong></summary>

**Preparazione backend per mapping e IP secondari.** Introdotti inventario e funzioni per gestire mapping statici TCP/UDP, insieme all'aggiunta non distruttiva di indirizzi IPv4 secondari. Non sono stati aggiunti nuovi controlli nella UI.

</details>

<details>
<summary><strong>1.12.1 — 15 ottobre 2026</strong></summary>

**Preflight più prudente per il NAT.** Distinzione fra NAT assente, già corretto e in conflitto; blocco del Commit in presenza di configurazioni incompatibili o di stato ICS non verificabile.

</details>

<details>
<summary><strong>1.12.0 — 15 ottobre 2026</strong></summary>

**Commit differenziale e idempotente.** “Configura gateway” confronta la configurazione candidata con lo stato effettivo di Windows e applica soltanto le differenze residue. Un Commit parzialmente riuscito conserva il candidato per un nuovo tentativo; vengono verificate la convergenza finale e le transizioni di stato locali in `%LOCALAPPDATA%\WinNAT-UI\commit-states`.

</details>

<details>
<summary><strong>1.11.2 — 15 ottobre 2026</strong></summary>

**Segnalazione bug meno dipendente da GitHub pubblico.** La segnalazione viene inoltrata al gateway anche se la lettura pubblica delle Issue non è disponibile; il servizio gateway doveva ancora essere configurato dal manutentore.

</details>

<details>
<summary><strong>1.11.1 — 15 ottobre 2026</strong></summary>

**Messaggi di errore del reporting più chiari.** Eliminata una seconda finestra di errore ricorsiva; in caso di gateway assente o non disponibile il report anonimizzato rimane copiabile.

</details>

<details>
<summary><strong>1.11.0 — 15 ottobre 2026</strong></summary>

**Sistema di tracciamento dei bug.** Aggiunti archivio locale, firma anonima per riconoscere problemi simili, monitoraggio dello stato delle Issue e notifiche sulla disponibilità di versioni correttive. La creazione anonima dipendeva dall'attivazione del backend, completata nella `1.14.0`.

</details>

<details>
<summary><strong>1.10.2 — 15 ottobre 2026</strong></summary>

**Segnalazione guidata degli errori.** Nuove azioni per copiare l'errore oppure aprire una bozza di Issue GitHub contenente solo metadati predefiniti e anonimizzati. Nessuna pubblicazione automatica della bozza.

</details>

<details>
<summary><strong>1.10.1 — 15 ottobre 2026</strong></summary>

**Console PowerShell nel Commit.** Mostra script eseguiti, STDOUT, STDERR e codici di uscita; le informazioni restano consultabili anche durante gli errori e il rollback.

</details>

<details>
<summary><strong>1.10.0 — 15 ottobre 2026</strong></summary>

**Updater integrato e identità grafica.** Controllo delle release stabili GitHub, download dello ZIP ufficiale con consenso esplicito, verifica SHA-256, backup preventivo e tentativo di ripristino. Introdotta inoltre l'icona dell'applicazione nell'eseguibile e nella UI. **Limite storico:** l'updater non risultava collaudato su un computer Windows reale.

</details>

<details>
<summary><strong>1.9.0 — 14 ottobre 2026</strong></summary>

**Supporto WAN dinamiche e LAN automatica.** Include le funzionalità della versione sorgente intermedia non pubblicata, più le correzioni di stabilità.

**Anteprima gateway più stabile.** Ignorate alcune variazioni temporanee delle WAN dinamiche durante la verifica tra anteprima e Commit, mantenendo i controlli sulla configurazione realmente rilevante.

</details>

<details>
<summary><strong>1.8.0 — 14 ottobre 2026</strong></summary>

**Rollback compensativo delle modifiche di rete.** In caso di Commit fallito, l'app tenta il ripristino delle risorse coinvolte tramite snapshot e verifica l'esito. **Limite:** non equivale a una transazione atomica di Windows e non garantisce il ripristino delle sessioni NAT o di tutte le modifiche esterne.

</details>

<details>
<summary><strong>1.7.0 — 14 ottobre 2026</strong></summary>

**Diagnostica di compatibilità in sola lettura.** Introdotto `tools/WinNAT-Diagnostica.ps1`, con inventario del sistema, schede, IPv4, route, WinNAT, ICS e Hyper-V e report TXT/JSON.

</details>

<details>
<summary><strong>Serie 1.6.x e correzione 1.5.2 — 14 ottobre 2026</strong></summary>

- **1.6.4:** errori PowerShell più leggibili, correzione dei caratteri accentati, allineamento delle note di rilascio e centralizzazione del numero di versione.
- **1.6.3:** diagnostica PowerShell completa con script numerati, stdout, stderr e timeout.
- **1.6.2:** corretta la gestione di falsi errori quando si applica l'IPv4 statico LAN.
- **1.6.1:** introdotta una finestra per copiare i dettagli di debug.
- **1.6.0:** nuova interfaccia laterale, dashboard con topologia, tema chiaro/scuro e barra delle modifiche; risolto un caso di ripristino DHCP. Pubblicata come MINOR nella nuova sequenza.
- **1.5.2:** corretti casi di conflitto fra DHCP, PersistentStore e IP statico LAN; questa versione conservava ancora la vecchia interfaccia.

</details>

<details>
<summary><strong>Versioni 1.5.0–1.5.1 — 14 ottobre 2026</strong></summary>

- **1.5.1:** primo intervento sul conflitto PersistentStore/DHCP e test regressione.
- **1.5.0:** configurazione completa di un gateway Windows da computer non configurato, con LAN, WAN, metriche, routing IPv4, forwarding e NAT; disponibili Disabilita e Ripristina.

</details>

<details>
<summary><strong>Serie iniziale</strong></summary>

- **1.4.0 — 14 ottobre 2026:** gestione della rimozione di NAT creati esternamente all'app e inventario concorrente.
- **1.3.0 — 14 ottobre 2026:** dashboard, modifiche candidate, Commit, sessioni NAT e avanzamento operazioni.
- **1.2.0 — 14 ottobre 2026:** prima distribuzione binaria pubblica con modifiche pendenti e Commit; il titolo della finestra conteneva un errore di numerazione.

</details>
