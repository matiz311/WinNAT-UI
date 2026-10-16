# WinNAT-UI — Note di rilascio

Le note di questa pagina sono destinate agli utilizzatori dell'applicazione. Per i dettagli delle singole modifiche, i limiti tecnici e la cronologia completa consultare [CHANGELOG.md](CHANGELOG.md). Le versioni sono mantenute con i loro numeri originali: questa documentazione non modifica tag, asset o versioni degli eseguibili già distribuiti.

> **Importante:** WinNAT-UI modifica routing, indirizzi IPv4 e Windows NAT. Prima di applicare configurazioni su computer utilizzati per l'accesso remoto, verificare di disporre di un accesso locale e di una procedura di ripristino. Le operazioni che ricreano WinNAT possono interrompere sessioni NAT attive.

## 1.10.0 — 16 ottobre 2026

**Tema del rilascio: segnalazione anonima dei problemi e diagnostica degli aggiornamenti.**

### Novità
- Attivato il gateway Cloudflare per inviare segnalazioni di bug senza richiedere un account GitHub all'utente. L'endpoint viene distribuito e verificato tramite GitHub Actions.
- Introdotti controlli di salute del servizio, limitazione della frequenza di invio e convalida dei soli metadati previsti. Il gateway conserva le credenziali GitHub sul server anziché nel client.
- Aggiunto un test end-to-end del servizio che invia una segnalazione sintetica, verifica il rilevamento dei duplicati e chiude la Issue di prova.

### Correzioni e affidabilità
- Gestiti i ritardi di indicizzazione delle Issue GitHub per ridurre la creazione di segnalazioni duplicate.
- Accettate versioni sia a tre componenti (es. `1.10.0`) sia HOTFIX a quattro componenti (es. `1.9.15.1`).
- Il controllo manuale degli aggiornamenti restituisce messaggi più specifici quando i metadati della release non sono validi; il controllo automatico all'avvio resta non bloccante in caso di indisponibilità del servizio.

### Compatibilità e limiti
- Nessuna modifica intenzionale alla logica di NAT e routing rispetto alla `1.9.15.1`.
- Le segnalazioni automatiche inviano soltanto metadati anonimizzati predefiniti: non vengono inoltrati automaticamente configurazioni, comandi, credenziali o output PowerShell grezzi.
- I test CI e del gateway non sostituiscono il collaudo su una macchina Windows reale, in particolare per l'aggiornamento dell'app e la riconfigurazione di rete.

## 1.9.15.1 — 15 ottobre 2026 — HOTFIX

**Correzione mirata di “Aggiungi NAT”.** Il comando crea la regola richiesta tramite `New-NetNat` senza ricostruire altri oggetti NAT, espandere prefissi o intervenire sugli indirizzi LAN/WAN. Se nome e prefisso coincidono con una regola esistente, l'operazione non ripete modifiche; se il nome collide con una configurazione diversa, viene segnalato il conflitto. Il rollback resta limitato all'oggetto richiesto. Aggiunto il supporto infrastrutturale al numero di versione HOTFIX a quattro componenti.

## 1.9.15 — 15 ottobre 2026

**Aggregazione di subnet LAN in una sola istanza WinNAT.** I percorsi di configurazione gateway possono espandere il prefisso dell'istanza WinNAT per comprendere più subnet, cercando di preservare nome, mapping statici e parametri supportati. Il Commit espone l'impatto della ricreazione dell'istanza e il rollback tenta di ripristinare il prefisso precedente. **Attenzione:** la successiva `1.9.15.1` ha deliberatamente separato il comportamento dell'azione semplice “Aggiungi NAT”, che non effettua più questa espansione.

## 1.9.14 — 15 ottobre 2026

**Migliorata la coesistenza di più subnet.** Riutilizzo di un'istanza WinNAT quando il suo prefisso include la LAN richiesta; aggiunta di IPv4 LAN senza sostituire indirizzi preesistenti e conservazione delle route non interessate dall'operazione. Se il prefisso NAT non è sufficiente, il Commit non procede a un reset implicito.

## 1.9.13 — 15 ottobre 2026

**Semplificata la creazione NAT.** Rimossi alcuni blocchi preventivi globali sul numero di istanze; rimangono i controlli sui nomi duplicati e la verifica dell'esito PowerShell. Questa versione è storica: consultare la `1.9.15.1` per il comportamento corretto di “Aggiungi NAT”.

## 1.9.12 — 15 ottobre 2026

**Correzione packaging Windows.** Incluso esplicitamente il modulo backend NAT/IP nell'eseguibile PyInstaller.

## 1.9.11 — 15 ottobre 2026

**Preparazione backend per mapping e IP secondari.** Introdotti inventario e funzioni per gestire mapping statici TCP/UDP, insieme all'aggiunta non distruttiva di indirizzi IPv4 secondari. Non sono stati aggiunti nuovi controlli nella UI.

## 1.9.10 — 15 ottobre 2026

**Preflight più prudente per il NAT.** Distinzione fra NAT assente, già corretto e in conflitto; blocco del Commit in presenza di configurazioni incompatibili o di stato ICS non verificabile.

## 1.9.9 — 15 ottobre 2026

**Commit differenziale e idempotente.** “Configura gateway” confronta la configurazione candidata con lo stato effettivo di Windows e applica soltanto le differenze residue. Un Commit parzialmente riuscito conserva il candidato per un nuovo tentativo; vengono verificate la convergenza finale e le transizioni di stato locali in `%LOCALAPPDATA%\WinNAT-UI\commit-states`.

## 1.9.8 — 15 ottobre 2026

**Segnalazione bug meno dipendente da GitHub pubblico.** La segnalazione viene inoltrata al gateway anche se la lettura pubblica delle Issue non è disponibile; il servizio gateway doveva ancora essere configurato dal manutentore.

## 1.9.7 — 15 ottobre 2026

**Messaggi di errore del reporting più chiari.** Eliminata una seconda finestra di errore ricorsiva; in caso di gateway assente o non disponibile il report anonimizzato rimane copiabile.

## 1.9.6 — 15 ottobre 2026

**Sistema di tracciamento dei bug.** Aggiunti archivio locale, firma anonima per riconoscere problemi simili, monitoraggio dello stato delle Issue e notifiche sulla disponibilità di versioni correttive. La creazione anonima dipendeva dall'attivazione del backend, completata nella `1.10.0`.

## 1.9.5 — 15 ottobre 2026

**Segnalazione guidata degli errori.** Nuove azioni per copiare l'errore oppure aprire una bozza di Issue GitHub contenente solo metadati predefiniti e anonimizzati. Nessuna pubblicazione automatica della bozza.

## 1.9.4 — 15 ottobre 2026

**Console PowerShell nel Commit.** Mostra script eseguiti, STDOUT, STDERR e codici di uscita; le informazioni restano consultabili anche durante gli errori e il rollback.

## 1.9.3 — 15 ottobre 2026

**Updater integrato e identità grafica.** Controllo delle release stabili GitHub, download dello ZIP ufficiale con consenso esplicito, verifica SHA-256, backup preventivo e tentativo di ripristino. Introdotta inoltre l'icona dell'applicazione nell'eseguibile e nella UI. **Limite storico:** l'updater non risultava collaudato su un computer Windows reale.

## 1.9.2 — 14 ottobre 2026

**Anteprima gateway più stabile.** Ignorate alcune variazioni temporanee delle WAN dinamiche durante la verifica tra anteprima e Commit, mantenendo i controlli sulla configurazione realmente rilevante.

## 1.9.1 — 14 ottobre 2026

**Più WAN e rilevamento automatico della LAN.** WAN aggiungibili dinamicamente, ordinabili per priorità e metriche; rilevamento degli indirizzi IPv4 LAN utilizzabili, valori iniziali di fallback e controllo contro subnet sovrapposte alle WAN. Conservata la compatibilità dei profili precedenti.

## 1.9.0 — 14 ottobre 2026

**Rollback compensativo delle modifiche di rete.** In caso di Commit fallito, l'app tenta il ripristino delle risorse coinvolte tramite snapshot e verifica l'esito. **Limite:** non equivale a una transazione atomica di Windows e non garantisce il ripristino delle sessioni NAT o di tutte le modifiche esterne.

## 1.8.0 — 14 ottobre 2026

**Diagnostica di compatibilità in sola lettura.** Introdotto `tools/WinNAT-Diagnostica.ps1`, con inventario del sistema, schede, IPv4, route, WinNAT, ICS e Hyper-V e report TXT/JSON.

## Serie 1.7.x — 14 ottobre 2026

- **1.7.5:** errori PowerShell più leggibili, correzione dei caratteri accentati, allineamento delle note di rilascio e centralizzazione del numero di versione.
- **1.7.4:** diagnostica PowerShell completa con script numerati, stdout, stderr e timeout.
- **1.7.3:** corretta la gestione di falsi errori quando si applica l'IPv4 statico LAN.
- **1.7.2:** introdotta una finestra per copiare i dettagli di debug.
- **1.7.1:** nuova interfaccia laterale, dashboard con topologia, tema chiaro/scuro e barra delle modifiche; risolto un caso di ripristino DHCP. **Classificazione storica anomala:** per ampiezza funzionale avrebbe meritato una MINOR.
- **1.7.0:** corretti casi di conflitto fra DHCP, PersistentStore e IP statico LAN; questa versione conservava ancora la vecchia interfaccia.

## Serie 1.6.x — 14 ottobre 2026

- **1.6.1:** primo intervento sul conflitto PersistentStore/DHCP e test regressione.
- **1.6.0:** configurazione completa di un gateway Windows da computer non configurato, con LAN, WAN, metriche, routing IPv4, forwarding e NAT; disponibili Disabilita e Ripristina.

## Serie iniziale

- **1.4.0 — 14 ottobre 2026:** gestione della rimozione di NAT creati esternamente all'app e inventario concorrente.
- **1.3.0 — 14 ottobre 2026:** dashboard, modifiche candidate, Commit, sessioni NAT e avanzamento operazioni.
- **1.2.0 — 14 ottobre 2026:** prima distribuzione binaria pubblica con modifiche pendenti e Commit; il titolo della finestra indicava erroneamente `1.1.0`.

## Numerazioni storiche particolari

- **1.5.0:** versione saltata, non distribuita.
- **1.10.1 del 14 ottobre 2026:** pubblicazione erronea successivamente ritirata; la versione corretta era `1.9.2`. Questa voce **non** rappresenta una release successiva all'attuale `1.10.0`.
- **1.10.0:** una precedente build con tale numero era stata annullata; il numero è stato poi riutilizzato per il rilascio candidato del 16 ottobre 2026. Distinguere build annullate e release effettivamente pubblicate consultando i tag e gli asset GitHub.

## Politica per i prossimi rilasci

- `1.10.0+ci.<run>.<sha>`: nuova build dello stesso codice/versione funzionale.
- `1.10.0.1`: HOTFIX strettamente correttivo e compatibile con i sistemi di aggiornamento attuali.
- `1.10.1`: correzioni e stabilizzazione compatibili, dopo la `1.10.0`.
- `1.11.0`: insieme coerente di nuove capacità retrocompatibili.
- `2.0.0`: cambiamenti incompatibili che richiedano migrazione documentata.

Gli identificativi storici non vengono riscritti. La classificazione viene corretta per il futuro, non retroattivamente sui file distribuiti.
