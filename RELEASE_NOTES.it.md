# WinNAT-UI — Note di rilascio

Le note di questa pagina sono destinate agli utilizzatori dell'applicazione. Per i dettagli delle singole modifiche, i limiti tecnici e la cronologia completa consultare [CHANGELOG.md](CHANGELOG.md). I numeri riportati corrispondono alle **33 GitHub Releases**, fino alla versione pubblicata **v1.16.0**. Il 16 ottobre 2026 la cronologia delle 28 release precedenti è stata rinumerata e i relativi eseguibili ricompilati; non utilizzare riferimenti della numerazione precedente.

> **Importante:** WinNAT-UI modifica routing, indirizzi IPv4 e Windows NAT. Prima di applicare configurazioni su computer utilizzati per l'accesso remoto, verificare di disporre di un accesso locale e di una procedura di ripristino. Le operazioni che ricreano WinNAT possono interrompere sessioni NAT attive.

## 1.16.0 — 17 ottobre 2026

**Gestione dei bug e maggiore affidabilità degli aggiornamenti.** In **Informazioni → Bug segnalati** si aggiungono titoli descrittivi, stati di triage, priorità, data di aggiornamento, filtri e ricerca. La cronologia locale rimane consultabile anche senza connessione a GitHub.

L'updater distingue problemi del servizio remoto e metadati invalidi, permette di segnalare al riavvio un aggiornamento fallito e predispone la finestra di avanzamento prima della chiusura della UI. È stato introdotto un registro delle manutenzioni con controllo CI dedicato.

**Limiti:** il Worker è stato distribuito e il controllo `/health` ha restituito `ready`; le etichette di triage GitHub richiedono verifica operativa. I percorsi di installazione, rollback e rete devono ancora essere collaudati su Windows reale. L'eseguibile resta non firmato.

La **v1.16.0 è pubblicata** sulla [pagina GitHub Releases](https://github.com/matiz311/WinNAT-UI/releases/tag/v1.16.0), con archivio Windows e digest SHA-256 verificabile.

## 1.15.1 — 16 ottobre 2026

**Patch del logo Windows.** In caso di errore nel caricamento dell'icona ICO, WinNAT-UI tenta comunque di applicare l'icona PNG derivata dallo stesso logo vettoriale alle finestre Tk. Nessuna variazione delle funzioni NAT o della configurazione della rete.

## 1.15.0 — 16 ottobre 2026

**Tema: configurazione LAN più flessibile, diagnostica completa e nuova identità visiva.**

### Novità
- Ridimensionamento della finestra più fluido, con meno ricalcoli di layout e disegni della topologia.
- Un'interfaccia LAN che utilizza DHCP può essere preparata per il passaggio a IP statico, scegliendo indirizzo/prefisso oppure mantenendo il valore proposto.
- Aggiunta e gestione di IPv4 secondari sulla LAN tramite interfaccia grafica.
- Nuova icona vettoriale nei formati Windows, con migliore leggibilità anche nella barra delle applicazioni.
- Invio bug guidato da una finestra di avanzamento, con report ricchi di informazioni utili per il troubleshooting.
- Installazione degli aggiornamenti accompagnata da una finestra di avanzamento dedicata.

### Correzioni e compatibilità
- Corretta la disposizione su più righe del testo nella finestra di conferma aggiornamento.
- Rilevamento coerente di DHCP e IPv4 primario/secondario, senza modificare in modo implicito altri indirizzi della scheda.
- Diagnostica specifica per risposte HTTP 404, 403, 429 e 5xx, errori DNS e timeout nel controllo aggiornamenti, includendo quanto preparato per la v1.14.1.
- Continua a essere supportata una sola istanza fisica WinNAT; non viene introdotta la proposta multi-oggetto della PR #37.

### Privacy e collaudo
Le segnalazioni di bug possono includere topologie, IP, output PowerShell e traceback potenzialmente sensibili. La pubblicazione su GitHub avviene **solo dopo conferma esplicita**; controllare l'anteprima prima di inviare. La mascheratura automatica dei dati identificativi è solo parziale.
La CI Windows non prova da sola l'applicazione di configurazioni IP su una macchina reale, il rollback e l'aggiornamento completo; questi percorsi richiedono collaudo su host Windows con accesso locale.

**Collaudo:** build e test CI Windows superati; la validazione su dispositivi reali rimane distinta dalla pubblicazione del pacchetto.

## 1.14.1 — 16 ottobre 2026

**Correzione di manutenzione del controllo aggiornamenti.** Le risposte HTTP 404, 403/429 e 5xx di GitHub vengono distinte da errori di connessione/DNS/proxy e mostrate con indicazioni operative. Il controllo silenzioso all'avvio rimane non bloccante. Nessuna variazione intenzionale a NAT, LAN/WAN, interfaccia grafica o gestione degli IP secondari. L'updater mantiene tutte le verifiche di autenticità e SHA-256 già previste.

## 1.14.0 — 16 ottobre 2026

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

## 1.13.0.1 — 15 ottobre 2026 — HOTFIX

**Correzione mirata di “Aggiungi NAT”.** Il comando crea la regola richiesta tramite `New-NetNat` senza ricostruire altri oggetti NAT, espandere prefissi o intervenire sugli indirizzi LAN/WAN. Se nome e prefisso coincidono con una regola esistente, l'operazione non ripete modifiche; se il nome collide con una configurazione diversa, viene segnalato il conflitto. Il rollback resta limitato all'oggetto richiesto. Aggiunto il supporto infrastrutturale al numero di versione HOTFIX a quattro componenti.

## 1.13.0 — 15 ottobre 2026

**Aggregazione di subnet LAN in una sola istanza WinNAT.** I percorsi di configurazione gateway possono espandere il prefisso dell'istanza WinNAT per comprendere più subnet, cercando di preservare nome, mapping statici e parametri supportati. Il Commit espone l'impatto della ricreazione dell'istanza e il rollback tenta di ripristinare il prefisso precedente. **Attenzione:** la successiva `1.13.0.1` ha deliberatamente separato il comportamento dell'azione semplice “Aggiungi NAT”, che non effettua più questa espansione.

## 1.12.5 — 15 ottobre 2026

**Migliorata la coesistenza di più subnet.** Riutilizzo di un'istanza WinNAT quando il suo prefisso include la LAN richiesta; aggiunta di IPv4 LAN senza sostituire indirizzi preesistenti e conservazione delle route non interessate dall'operazione. Se il prefisso NAT non è sufficiente, il Commit non procede a un reset implicito.

## 1.12.4 — 15 ottobre 2026

**Semplificata la creazione NAT.** Rimossi alcuni blocchi preventivi globali sul numero di istanze; rimangono i controlli sui nomi duplicati e la verifica dell'esito PowerShell. Questa versione è storica: consultare la `1.13.0.1` per il comportamento corretto di “Aggiungi NAT”.

## 1.12.3 — 15 ottobre 2026

**Correzione packaging Windows.** Incluso esplicitamente il modulo backend NAT/IP nell'eseguibile PyInstaller.

## 1.12.2 — 15 ottobre 2026

**Preparazione backend per mapping e IP secondari.** Introdotti inventario e funzioni per gestire mapping statici TCP/UDP, insieme all'aggiunta non distruttiva di indirizzi IPv4 secondari. Non sono stati aggiunti nuovi controlli nella UI.

## 1.12.1 — 15 ottobre 2026

**Preflight più prudente per il NAT.** Distinzione fra NAT assente, già corretto e in conflitto; blocco del Commit in presenza di configurazioni incompatibili o di stato ICS non verificabile.

## 1.12.0 — 15 ottobre 2026

**Commit differenziale e idempotente.** “Configura gateway” confronta la configurazione candidata con lo stato effettivo di Windows e applica soltanto le differenze residue. Un Commit parzialmente riuscito conserva il candidato per un nuovo tentativo; vengono verificate la convergenza finale e le transizioni di stato locali in `%LOCALAPPDATA%\WinNAT-UI\commit-states`.

## 1.11.2 — 15 ottobre 2026

**Segnalazione bug meno dipendente da GitHub pubblico.** La segnalazione viene inoltrata al gateway anche se la lettura pubblica delle Issue non è disponibile; il servizio gateway doveva ancora essere configurato dal manutentore.

## 1.11.1 — 15 ottobre 2026

**Messaggi di errore del reporting più chiari.** Eliminata una seconda finestra di errore ricorsiva; in caso di gateway assente o non disponibile il report anonimizzato rimane copiabile.

## 1.11.0 — 15 ottobre 2026

**Sistema di tracciamento dei bug.** Aggiunti archivio locale, firma anonima per riconoscere problemi simili, monitoraggio dello stato delle Issue e notifiche sulla disponibilità di versioni correttive. La creazione anonima dipendeva dall'attivazione del backend, completata nella `1.14.0`.

## 1.10.2 — 15 ottobre 2026

**Segnalazione guidata degli errori.** Nuove azioni per copiare l'errore oppure aprire una bozza di Issue GitHub contenente solo metadati predefiniti e anonimizzati. Nessuna pubblicazione automatica della bozza.

## 1.10.1 — 15 ottobre 2026

**Console PowerShell nel Commit.** Mostra script eseguiti, STDOUT, STDERR e codici di uscita; le informazioni restano consultabili anche durante gli errori e il rollback.

## 1.10.0 — 15 ottobre 2026

**Updater integrato e identità grafica.** Controllo delle release stabili GitHub, download dello ZIP ufficiale con consenso esplicito, verifica SHA-256, backup preventivo e tentativo di ripristino. Introdotta inoltre l'icona dell'applicazione nell'eseguibile e nella UI. **Limite storico:** l'updater non risultava collaudato su un computer Windows reale.

## 1.9.0 — 14 ottobre 2026

**Supporto WAN dinamiche e LAN automatica.** Include le funzionalità della versione sorgente intermedia non pubblicata, più le correzioni di stabilità.

**Anteprima gateway più stabile.** Ignorate alcune variazioni temporanee delle WAN dinamiche durante la verifica tra anteprima e Commit, mantenendo i controlli sulla configurazione realmente rilevante.

## 1.8.0 — 14 ottobre 2026

**Rollback compensativo delle modifiche di rete.** In caso di Commit fallito, l'app tenta il ripristino delle risorse coinvolte tramite snapshot e verifica l'esito. **Limite:** non equivale a una transazione atomica di Windows e non garantisce il ripristino delle sessioni NAT o di tutte le modifiche esterne.

## 1.7.0 — 14 ottobre 2026

**Diagnostica di compatibilità in sola lettura.** Introdotto `tools/WinNAT-Diagnostica.ps1`, con inventario del sistema, schede, IPv4, route, WinNAT, ICS e Hyper-V e report TXT/JSON.

## Serie 1.6.x e correzione 1.5.2 — 14 ottobre 2026

- **1.6.4:** errori PowerShell più leggibili, correzione dei caratteri accentati, allineamento delle note di rilascio e centralizzazione del numero di versione.
- **1.6.3:** diagnostica PowerShell completa con script numerati, stdout, stderr e timeout.
- **1.6.2:** corretta la gestione di falsi errori quando si applica l'IPv4 statico LAN.
- **1.6.1:** introdotta una finestra per copiare i dettagli di debug.
- **1.6.0:** nuova interfaccia laterale, dashboard con topologia, tema chiaro/scuro e barra delle modifiche; risolto un caso di ripristino DHCP. Pubblicata come MINOR nella nuova sequenza.
- **1.5.2:** corretti casi di conflitto fra DHCP, PersistentStore e IP statico LAN; questa versione conservava ancora la vecchia interfaccia.

## Versioni 1.5.0–1.5.1 — 14 ottobre 2026

- **1.5.1:** primo intervento sul conflitto PersistentStore/DHCP e test regressione.
- **1.5.0:** configurazione completa di un gateway Windows da computer non configurato, con LAN, WAN, metriche, routing IPv4, forwarding e NAT; disponibili Disabilita e Ripristina.

## Serie iniziale

- **1.4.0 — 14 ottobre 2026:** gestione della rimozione di NAT creati esternamente all'app e inventario concorrente.
- **1.3.0 — 14 ottobre 2026:** dashboard, modifiche candidate, Commit, sessioni NAT e avanzamento operazioni.
- **1.2.0 — 14 ottobre 2026:** prima distribuzione binaria pubblica con modifiche pendenti e Commit; il titolo della finestra conteneva un errore di numerazione.


## Regole di pubblicazione

- **MINOR:** `1.14.0` — funzionalità retrocompatibili con riepilogo, compatibilità, test e correzioni.
- **PATCH:** `1.14.1` — manutenzione e correzioni ordinarie.
- **HOTFIX:** `1.14.0.1` — correzione urgente e circoscritta; quarto numero riservato agli HOTFIX.
- **BUILD:** `1.14.0+ci.<run>.<sha>` — ricompilazione senza nuova versione funzionale.

**Stato della distribuzione:** la migrazione delle 28 release precedenti è stata completata e la `v1.14.0` è stata pubblicata il 16 ottobre 2026. Tutte le versioni di questa pagina usano la numerazione ufficiale corrente. Per le regole di versioning consulta [VERSIONING_POLICY.md](VERSIONING_POLICY.md); per i pacchetti disponibili usa [GitHub Releases](https://github.com/matiz311/WinNAT-UI/releases).
