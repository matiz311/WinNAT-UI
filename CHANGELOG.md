# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/); versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

Regole del progetto (dettagli in [VERSIONING_POLICY.md](VERSIONING_POLICY.md)):
- **MAJOR**: cambio incompatibile; approvazione manuale e riepilogo significativo obbligatori.
- **MINOR**: pacchetto significativo di feature e correzioni: non incrementare per singole patch o a ogni build; richiede le sezioni **Sintesi**, **Funzionalità** e **Correzioni**, oltre all'approvazione manuale.
- **PATCH**: correzioni e stabilizzazione della serie corrente, senza nuove funzionalità significative.
- **BUILD**: ogni esecuzione GitHub Actions genera un artifact identificato con run number e SHA, senza incrementare la versione funzionale.
- La versione è definita in `version.py`; tag e note si generano solo per una release autorizzata. I tag già pubblicati nella numerazione corrente non vengono modificati; la normalizzazione dello storico è stata conclusa il 16 ottobre 2026.


## [1.16.0] - 2026-10-17 (candidato)
### Sintesi
Release MINOR retrocompatibile: ricerca e triage dei bug segnalati, diagnosi più precisa del canale GitHub e aggiornamenti Windows più affidabili. Comprende le correzioni integrate dopo v1.15.1 e lascia invariata l'architettura WinNAT a singola subnet interna.

### Funzionalità
- Informazioni → Bug segnalati: titolo descrittivo della Issue, stato di triage, priorità, data di aggiornamento, release correttiva, ricerca per titolo/ID e filtri di stato (PR #67).
- Le nuove segnalazioni del gateway includono la label iniziale `triage:ricevuto`; l'attivazione effettiva richiede deploy del Worker e verifica delle label GitHub (PR #67).
- Registro manutenzioni GitHub con controllo CI preventivo; lo stato non equivale a una verifica di salute live dei servizi (PR #68).

### Correzioni
- La sincronizzazione Issue gestisce errori DNS, timeout, TLS e HTTP preservando lo storico locale (PR #69).
- Errori GitHub e metadati asset updater sono classificati in modo strutturato; gli indizi di manutenzione non aggirano verifica URL e SHA256 (PR #70).
- Un aggiornamento fallito salva diagnosi locali e le presenta una volta al riavvio, con segnalazione opt-in (PR #62).
- La finestra di aggiornamento viene predisposta prima della chiusura dell'app, con timeout di ripiego (PR #71).
- Il guard esclude test e documentazione del gateway dal perimetro dei cambiamenti che possono interrompere il servizio, mantenendo protetti sorgenti e deploy (PR #67/#72).

### Limiti
- Serve collaudo reale su Windows per installazione, rollback e rete; la CI esegue anche test, packaging, diagnostica e Defender, ma non replica tutti gli scenari operativi.
- Le modifiche Worker richiedono pubblicazione/verifica del gateway; la UI non dipende dalla disponibilità del registro manutenzioni.
- Eseguibile non firmato digitalmente.

## [1.15.1] - 2026-10-16
### Correzioni
- Il caricamento dell'icona PNG derivata dal logo vettoriale resta indipendente dall'icona Windows ICO: se l'API ICO non è disponibile o restituisce un errore, la barra del titolo e i dialoghi Tk possono ancora usare il logo PNG.
- Nessuna modifica alla logica WinNAT, alle impostazioni di rete o al formato dei dati.

## [1.15.0] - 2026-10-16
### Sintesi
Release funzionale retrocompatibile della serie 1.x: migliora la configurazione LAN, estende la gestione degli indirizzi IPv4, rende le segnalazioni dei problemi più diagnostiche e perfeziona l'esperienza di aggiornamento. Include una nuova icona vettoriale. Rimane invariato il vincolo architetturale di un'unica istanza fisica WinNAT.

### Funzionalità
- Ridimensionamento più fluido delle pagine: aggregazione degli eventi di larghezza e aggiornamenti condizionati di wrapping, canvas topologia e ScrollFrame per ridurre ridisegni ridondanti (PR #59).
- La configurazione guidata della LAN rileva il DHCP attivo e propone la conversione esplicita a IPv4 statico, con possibilità di scegliere indirizzo e prefisso, senza bloccare la preparazione delle modifiche per il solo DHCP.
- Gestione degli IPv4 secondari direttamente dall'interfaccia LAN, conservando l'indirizzo primario e rispettando il modello single-WinNAT.
- Segnalazioni di bug opzionali più dettagliate con contesto d'errore, traceback, output e configurazione di rete; anteprima e conferma esplicita prima della pubblicazione di informazioni potenzialmente sensibili su GitHub.
- Visualizzazione di avanzamento durante l'invio di segnalazioni e finestra Windows dedicata alle fasi dell'aggiornamento automatico.
- Nuova icona piatta in stile vettoriale, con risoluzioni dedicate per 16/32 pixel e asset ICO/PNG/SVG coordinati.

### Correzioni
- Corrette le interruzioni di riga nella conferma di aggiornamento, prima mostrate come sequenze letterali (PR #57).
- Migliorata la selezione dell'IPv4 LAN primario in presenza di indirizzi secondari e il trattamento degli indirizzi assegnati via DHCP nei piani di setup.
- Conservati i messaggi di errore e il flusso di conferma dei report durante le operazioni in background; ampliati i test d'integrazione.
- Classificazione degli errori HTTP e di connessione nel controllo aggiornamenti GitHub (404, 403/429, 5xx, DNS e timeout), incorporando il fix previsto nella manutenzione 1.14.1.
- L'aggiornamento continua a verificare provenienza e digest SHA-256 del pacchetto; il ripristino dei file rimane separato dalle configurazioni di rete.

### Limitazioni di collaudo
La CI Windows copre test unitari, PowerShell di sola lettura, packaging e scansione Defender. Non sostituisce la validazione su hardware reale delle transizioni DHCP→statico, degli IP secondari e di un aggiornamento completo da EXE.

## [1.14.1] - 2026-10-16
### Correzioni
- Gestione esplicita dei fallimenti HTTP durante il controllo degli aggiornamenti GitHub: distingue assenza di release stabile (404), accesso limitato (403/429), errori temporanei del servizio (5xx) e altri codici di risposta.
- Errori di connessione, DNS, proxy e timeout convertiti in messaggi comprensibili e non bloccanti all'avvio; il controllo manuale mostra un avviso senza creare una segnalazione di errore generica.
- Aggiunti test di regressione con risposte HTTP simulate. Le verifiche di URL ufficiale e SHA-256 degli aggiornamenti restano invariate.

## [1.14.0] - 2026-10-16
### Sintesi
WinNAT-UI completa il canale di segnalazione anonima introdotto nella serie precedente: il backend Cloudflare è ora distribuito e verificato end-to-end, con pubblicazione automatica dell'endpoint utilizzato dal client. La release consolida inoltre la diagnostica dell'updater e la compatibilità con le versioni HOTFIX a quattro componenti. Non modifica la logica NAT/routing già presente nella 1.13.0.1.

### Funzionalità
- Deploy automatico del gateway anonimo tramite GitHub Actions e Cloudflare Worker, con controllo `/health` prima della pubblicazione dell'endpoint in `bug-service.json`.
- Smoke test live della catena completa: creazione di una Issue sintetica, verifica della deduplicazione e chiusura automatica della Issue di test.
- Rate limiting nativo Cloudflare per origine e globale, limite rigido della dimensione del payload e validazione allowlist dei soli metadati anonimizzati previsti.

### Correzioni
- Il gateway ritenta la ricerca delle Issue aperte per gestire il ritardo di indicizzazione GitHub ed evitare duplicati immediatamente dopo una nuova segnalazione.
- Il gateway accetta sia versioni `MAJOR.MINOR.PATCH` sia HOTFIX `MAJOR.MINOR.PATCH.HOTFIX`, inclusa la release HOTFIX 1.13.0.1.
- Il controllo manuale degli aggiornamenti trasforma gli errori di validazione dei metadati GitHub in un messaggio specifico e utilizzabile, senza classificarli come errore operativo generico.
- Il controllo silenzioso all'avvio resta non bloccante quando il servizio aggiornamenti non è disponibile.


## [1.13.0.1] - 2026-10-15
### Corretto
- **Aggiungi NAT:** esegue direttamente `New-NetNat` per il nome e prefisso richiesti, senza controllare quanti altri NAT siano presenti.
- Un NAT con nome e prefisso identici resta idempotente; solo la collisione dello stesso nome con configurazione diversa viene diagnosticata prima dell'invio a PowerShell.
- Nessuna espansione automatica, `Remove-NetNat`, ricostruzione di prefissi o modifica di IP LAN/WAN durante **Aggiungi NAT**. I percorsi avanzati «Configura gateway» mantengono logiche separate.
- Scope del rollback limitato al nome della regola appena richiesta: non comprende e non modifica altri NAT preesistenti.
- Supporto a versioni HOTFIX `1.x.y.z` in Windows, GitHub Actions, updater e policy di pubblicazione; aggiunti test regressione.

## [1.13.0] - 2026-10-15
### Aggiunto
- Aggiungi NAT e Configura gateway espandono automaticamente l'unica istanza WinNAT al minimo prefisso CIDR condiviso dalle subnet LAN richieste (es. 192.168.1.0/24 e 192.168.192.0/24 -> 192.168.0.0/16).
- La migrazione preserva nome, prefisso esterno, mapping TCP/UDP statici e parametri WinNAT supportati; raccoglie lo stato attuale, verifica il risultato e tenta il ripristino immediato in caso d'errore.
- Il Commit mostra l'impatto della ricreazione dell'istanza sulle sessioni NAT; non rinumera LAN/WAN né rimuove IP primari/secondari.
- Allineati anche i percorsi legacy LAN/WAN e setup affinché riutilizzino il NAT esistente anziché crearne un secondo.
- Il rollback include il WinNAT fisico e può ripristinare il suo prefisso precedente; copertura dei test su aggregazione e conservazione dei mapping.

## [1.12.5] - 2026-10-15
### Corretto
- Un'unica istanza fisica WinNAT può coprire più subnet logiche LAN. Aggiungi NAT e Configura gateway riutilizzano l'istanza quando il suo prefisso comprende la subnet richiesta, indipendentemente dal nome.
- Aggiunta IPv4 LAN non distruttiva mediante New-NetIPAddress; gli IP primari e secondari esistenti non vengono sostituiti con netsh.
- Applicazione gateway non elimina più automaticamente route LAN non gestite dall'operazione.
- Se il prefisso dell'istanza NAT esistente non copre una nuova subnet, il Commit preserva la configurazione e richiede un piano di espansione/migrazione del NAT; nessun reset implicito.
- Test di coesistenza /24 con NAT /16, conservazione degli IP e prevenzione di più istanze fisiche.

## [1.12.4] - 2026-10-15
### Corretto
- «Aggiungi NAT»: permette la creazione di un WinNAT distinto anche in presenza di altri oggetti NAT. Rileva soltanto duplicati di nome/configurazione; l'eventuale rifiuto operativo viene da Windows PowerShell.
- Verifica la presenza del NAT dopo la creazione e preserva lo snapshot pre-commit.
- Rimuove i blocchi globali sul numero di NAT dai percorsi Configura gateway, LAN/WAN e Setup, mantenendo il controllo di conflitto sul medesimo nome e prefisso.
- Nessuna rimozione automatica dei NAT preesistenti e nessuna nuova opzione visibile nella UI.

## [1.12.3] - 2026-10-15
### Corretto
- Include esplicitamente il modulo backend headless NAT/IP nell'eseguibile PyInstaller, senza nuove opzioni UI.

## [1.12.2] - 2026-10-15
### Aggiunto (solo backend)
- Inventario completo dei mapping statici WinNAT e funzioni idempotenti per configurare più port mapping TCP/UDP sull'unica rete WinNAT supportata da Windows.
- Funzione per aggiungere indirizzi IPv4 secondari su interfacce statiche, senza rimuovere gli IP già configurati e senza modificare i gateway.
- Rifiuto esplicito di NAT indipendenti con prefissi differenti, non supportati da WinNAT; verifiche su conflitti, DHCP e prefisso del mapping.
- Nuovi test automatici. Nessuna nuova opzione esposta nella UI.

## [1.12.1] - 2026-10-15
### Corretto
- «Aggiungi NAT» distingue configurazione assente, già identica (nessuna operazione necessaria) e NAT incompatibile o concorrente.
- In presenza di un NAT incompatibile il messaggio indica nome e prefisso effettivo e interrompe il Commit senza modificare o eliminare la configurazione esistente.
- Lo stato ICS non verificabile blocca il preflight; un errore di preflight non avvia un rollback inutile.
- Test automatici dei casi di no-op, conflitto NAT e verifica ICS.

## [1.12.0] - 2026-10-15
### Corretto
- **Commit idempotente a differenze:** «Configura gateway» tratta il candidato come stato desiderato, rilegge Windows al momento del Commit e applica soltanto IP/DHCP, route LAN, `IPEnableRouter`, forwarding, metriche WAN e WinNAT che non coincidono già con il target.
- Un NAT già presente con stesso nome e prefisso del candidato viene riutilizzato; NAT differenti o concorrenti continuano a bloccare l'applicazione.
- Dopo un Commit parzialmente riuscito il candidato non viene più scartato: al tentativo successivo viene ricalcolato il diff sullo stato reale, evitando di ripetere operazioni già completate.
- Verifica di convergenza dopo l'applicazione: il Commit è considerato riuscito soltanto se una nuova lettura non rileva operazioni ancora mancanti.

### Diagnostica
- Salvataggio locale degli stati `candidate-commit`, `pre-commit`, `post-commit` e, quando necessario, `post-rollback` in `%LOCALAPPDATA%\WinNAT-UI\commit-states`, oltre al backup usato dal rollback.
- L'anteprima delle Modifiche viene ricalcolata sulla configurazione rilevata più recente, così mostra il delta residuo invece della sequenza originaria completa.


## [1.11.2] - 2026-10-15
### Corretto
- L'invio di un bug non richiede più che la lettura pubblica dell'elenco delle Issue GitHub abbia successo: il gateway riceve direttamente il report e gestisce autonomamente i duplicati.
- Resta indispensabile attivare l'endpoint HTTPS nel manifesto `bug-service.json` e configurare sul server l'autenticazione GitHub; la release non rende disponibile da sola il backend.

## [1.11.1] - 2026-10-15
### Corretto
- Gli errori durante «Segnala bug» non generano più una seconda finestra generica con possibilità di segnalare nuovamente il medesimo errore.
- Se il servizio anonimo non è configurato oppure non è disponibile, viene mostrata una spiegazione specifica e il report originale anonimizzato rimane copiabile nella finestra iniziale.
- Controllo dell'endpoint eseguito in background per non bloccare l'interfaccia.

## [1.11.0] - 2026-10-15
### Aggiunto
- Archiviazione locale delle segnalazioni bug e identificazione delle Issue simili mediante firma stabile anonimizzata.
- Creazione anonima delle Issue senza account GitHub tramite gateway HTTPS con credenziali custodite esclusivamente sul server, previa attivazione da parte del manutentore.
- Nella pagina Informazioni, elenco dei bug segnalati, stato di apertura e versione di correzione; confronto con le release ufficiali all'avvio per avvisare quando una correzione diventa disponibile.
### Sicurezza e distribuzione
- Il client invia soltanto un payload limitato a campi predefiniti e non include alcun token GitHub, output grezzo, comando o configurazione. Il gateway convalida il payload, deduplica e limita le richieste; richiede comunque protezione WAF.
- Il servizio anonimo resta inattivo finché il maintainer non distribuisce il Worker Cloudflare e pubblica il suo endpoint nel manifesto `bug-service.json`. Nessuna Issue può essere creata automaticamente prima di tale configurazione.

## [1.10.2] - 2026-10-15
### Aggiunto
- Gli errori mostrano le azioni «Copia errore» e «Segnala bug su GitHub»: la seconda apre una bozza di Issue con dati anonimizzati, senza pubblicare nulla automaticamente.
- Il report è costruito esclusivamente con metadati predefiniti: versione, operazione, categoria, tipo di eccezione, codice di uscita PowerShell e nomi dei moduli dell'app coinvolti.
### Riservatezza
- Non vengono esportati automaticamente traceback grezzo, comandi, configurazioni, output di PowerShell, indirizzi IP, credenziali, percorsi o nomi delle interfacce. L'utente può verificare il report e aggiungere informazioni prima dell'invio.

## [1.10.1] - 2026-10-15
### Migliorato
- Nella scheda Modifiche, console PowerShell aggiornabile durante il commit: mostra ogni script, STDOUT, STDERR e il codice di uscita.
- Log leggibile e copiabile anche se il commit fallisce e viene tentato un rollback; senza logging delle raccolte inventario esterne al commit.

## [1.10.0] - 2026-10-15
### Aggiunto
- Controllo automatico all'avvio della release stabile ufficiale disponibile su GitHub e comando «Controlla aggiornamenti» nella pagina Informazioni.
- Download diretto dello ZIP ufficiale solo con consenso esplicito, verifica SHA256 rispetto ai metadati GitHub, protezioni contro archivi non sicuri e avvio dell'aggiornamento a programma chiuso.
- Backup preventivo dei file dell'applicazione e tentativo di ripristino in caso di errore di installazione. L'aggiornamento non parte in presenza di modifiche di rete in sospeso.
### Nota
- Il primo passaggio alla versione contenente l'updater va fatto con lo ZIP manuale. La funzione di aggiornamento automatico richiede l'eseguibile Windows e non è ancora collaudata su una macchina reale.

### Aggiunto
- Icona dell'applicazione: dispositivi della LAN che convergono nel gateway NAT e un'unica uscita verso Internet, nei colori dell'interfaccia. Usata per l'eseguibile, la barra del titolo, la barra delle applicazioni, le finestre di dialogo e il logo nella barra laterale.
- File `.ico` con 10 risoluzioni (16–256 px) e disegni semplificati per le dimensioni piccole; sorgenti SVG in `assets/` e `tools/build_icon.py` per rigenerarle.
- La build verifica che l'eseguibile abbia l'icona e che i file grafici siano inclusi.
### Corretto
- Controllo di pubblicazione: confronta la versione con l'ultima release pubblicata invece che con il commit precedente, che nella CI (checkout a profondità 1) non era disponibile e bloccava ogni release.

## [1.9.0] - 2026-10-14
### Corretto
- Impronta anteprima del gateway normalizzata anche con WAN dinamiche: ignora stato/velocità adattatori, AddressState, APIPA e route connesse generate automaticamente, preservando i controlli di sicurezza su IP LAN, gateway WAN, NAT, forwarding, metriche e interfacce.
- In caso di modifica effettiva tra anteprima e commit, il Debug identifica i gruppi di configurazione cambiati.
### Funzionalità incluse
- Include il supporto alle WAN dinamiche e la rilevazione automatica della subnet LAN, insieme alle correzioni di stabilità della verifica dell'anteprima.
## [1.8.0] - 2026-10-14
### Aggiunto
- Rollback compensativo automatico su commit non riusciti: ripristina esclusivamente le risorse di rete coinvolte (IPv4, DHCP, route esplicite, forwarding, metriche, WinNAT, IPEnableRouter) secondo lo snapshot iniziale.
- Verifica finale delle modifiche monitorate e report Debug con comandi eseguiti, errori e differenze residue. Se lo stato non è verificabile, segnala rollback incompleto.
### Limitazioni
- Non è una transazione di Windows: APIPA, sessioni NAT, mapping statici preesistenti, stato di rete esterno e modifiche contemporanee potrebbero non essere ripristinabili. Prima di ogni commit viene comunque salvato uno snapshot JSON.

## [1.7.0] - 2026-10-14
### Aggiunto
- `tools/WinNAT-Diagnostica.ps1`: diagnostica di compatibilità in sola lettura (sistema, schede, IPv4, route, WinNAT, ICS, Hyper-V) con verdetto e indicazione delle schede utilizzabili come LAN/WAN; produce un report `.txt` e `.json` da allegare alle segnalazioni. Eseguito in CI come smoke test.

## [1.6.4] - 2026-10-14
### Corretto
- Finestra d'errore: il riepilogo mostra il primo messaggio utile dello stderr invece delle intestazioni ("ESECUZIONE POWERSHELL NON RIUSCITA", exit code); finestra centrata, coerente con il tema chiaro/scuro, dettagli tecnici a scomparsa, Esc per chiudere. Anche il messaggio di stato nella barra laterale mostra una sola riga leggibile.
- Output PowerShell letto in UTF-8: nomi di schede e messaggi con lettere accentate non risultano più corrotti (code page OEM 850 su Windows in italiano).
- Introdotto l'allineamento delle note pubblicate al CHANGELOG tramite il workflow manuale "Sync release notes".
- Versioning: unica fonte in `version.py`; versione file Windows, tag e note di release derivati automaticamente e verificati dai test. Le note di release non sono più scritte a mano nel workflow (in passato v1.3.0 e v1.6.1 avevano note copiate da altre versioni).

## [1.6.3] - 2026-10-14
### Cambiato
- Errori PowerShell più completi: exit code, interprete, timeout, stderr e stdout integrali e script eseguito con righe numerate (per confrontare «In riga:X»).

## [1.6.2] - 2026-10-14
### Corretto
- IP statico LAN: `netsh` poteva segnalare un falso errore "oggetto già esistente"; ora lo stato reale della LAN viene verificato e i conflitti di indirizzo diagnosticati prima di considerare l'operazione fallita.

## [1.6.1] - 2026-10-14
### Aggiunto
- Finestra d'errore con dettagli di debug copiabili: output PowerShell completo (stdout/stderr, exit code) e traceback Python.

## [1.6.0] - 2026-10-14
### Cambiato
- Nuova interfaccia: navigazione laterale, Panoramica con verdetto sullo stato del gateway, schema topologico LAN → PC → WAN, validazione dei campi in tempo reale, barra delle modifiche persistente, tema chiaro/scuro.
### Corretto
- Ripristino del DHCP LAN idempotente quando il DHCP è già attivo.

## [1.5.2] - 2026-10-14
### Corretto
- IP statico LAN su schede con DHCP in PersistentStore (`netsh ... store=persistent`) e recupero dopo un Commit fallito.
### Nota
- Contiene ancora l'**interfaccia precedente**: il redesign grafico viene introdotto nella 1.6.0.

## [1.5.1] - 2026-10-14
### Corretto
- Prima correzione del conflitto PersistentStore/DHCP sull'IP statico LAN, con test di regressione.

## [1.5.0] - 2026-10-14
### Aggiunto
- Configurazione completa da PC vergine secondo la guida «NAT e Routing IPv4 su Windows 11»: LAN, WAN primaria e secondaria con metriche, IPEnableRouter, forwarding, NAT; Disabilita e Ripristina espliciti.

## [1.4.0] - 2026-10-14
### Aggiunto
- Rimozione di configurazioni NAT preesistenti create fuori dall'app; raccolta dell'inventario in parallelo.

## [1.3.0] - 2026-10-14
### Aggiunto
- Dashboard di configurazione, modifiche candidate con Commit, sessioni NAT separate, barra di avanzamento.

## [1.2.0] - 2026-10-14
### Aggiunto
- Prima release binaria pubblica: modifiche pendenti e Commit una alla volta.
### Nota
- La prima build presentava un'incoerenza nel titolo della finestra. Scheda Informazioni, risorse Windows e tag identificano correttamente la versione 1.2.0.


## Normalizzazione della cronologia — 16 ottobre 2026

La rinumerazione delle 28 release pubblicate in precedenza è **completata**: i tag, i sorgenti con versione aggiornata e gli archivi Windows ricompilati sono stati verificati e ripubblicati. La **v1.14.0 è pubblicata** come 29ª release della sequenza attuale. I numeri nelle sezioni di questo changelog sono gli identificativi ufficiali, consultabili nella [pagina Releases](https://github.com/matiz311/WinNAT-UI/releases); eventuali alias della vecchia numerazione non sono più riferimenti di distribuzione.
