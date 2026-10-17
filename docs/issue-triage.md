# WinNAT-UI — Guideline standard per analisi e gestione delle segnalazioni

**Ambito:** bug report ricevuti dall'app WinNAT-UI, Issue GitHub collegate, regressioni e riaperture.
**Applicazione:** obbligatoria per ChatGPT, Claude e manutentori che effettuano il triage.
**Riferimenti:** [AGENTS.md](../AGENTS.md), [Issue #66: lifecycle dei bug](https://github.com/matiz311/WinNAT-UI/issues/66), [Issue #65: esempio operativo](https://github.com/matiz311/WinNAT-UI/issues/65).

**Obiettivo:** a ogni fase devono essere distinguibili problema, impatto, diagnosi confermata o ipotetica, priorità, stato, responsabile, prossimo passo e, quando verificata, release risolutiva. Il triage non equivale automaticamente a sviluppare una correzione, fare un merge o pubblicare una release: valgono sempre i gate di AGENTS.md e VERSIONING_POLICY.md.

## 1. Principi obbligatori

1. **Evidenze prima delle conclusioni.** Distinguere sempre fatto osservato, ipotesi, causa confermata, fattori esclusi e prove ancora necessarie. Un errore DNS o HTTPS non prova un malfunzionamento di WinNAT.
2. **Identità tecnica stabile.** Conservare numero della Issue e fingerprint del report. Il titolo GitHub può e deve diventare descrittivo; non deduplicare problemi diversi solo perché riportano lo stesso messaggio o la stessa categoria.
3. **Decisioni visibili nella UI = label GitHub.** Le colonne di WinNAT-UI derivano da titolo, stato della Issue e label `triage:*`, `priority:*`, `fixed-in/v...`. I commenti tecnici non sostituiscono le label.
4. **Stati indipendenti.** GitHub `open/closed`, fase `triage:*`, correzione integrata, release pubblicata e collaudo funzionale sono fatti diversi. Non presentarli come sinonimi.
5. **Non inventare release.** La prima versione risolutiva deve essere provata tramite commit, tag, GitHub Release e relativo artifact. Build CI, PR e main non sono release.
6. **Diagnostica utile e pubblicazione proporzionata.** Trattenere traceback e log per l'analisi ma non duplicare inutilmente nei commenti pubblici credenziali, token, identità, indirizzi, intere tabelle di routing e topologia.

## 2. Procedura operativa

### A. Ricezione e riconoscimento

- Acquisire numero Issue, URL, versione WinNAT-UI, OS, operazione, componente, momento UTC, errore/traceback, contesto d'uso e aspettativa dell'utente.
- Cercare Issue esistenti e confrontare cause e percorsi, non soltanto stringhe o fingerprint. Conservare riferimenti delle occorrenze e indicare la Issue principale quando un duplicato è **dimostrato**.
- Su nuova Issue assegnare `triage:ricevuto` se non già assegnato dal gateway; passando all'analisi utilizzare `triage:in-analisi`, rimuovendo l'eventuale stato precedente.
- Assegnare un **titolo distintivo**, appena le evidenze lo consentono: `[Bug][Componente] Sintomo e contesto specifico`. Evitare titoli indistinguibili come «Errore operativo non classificato». Non affermare cause non ancora verificate.

### B. Analisi preliminare e priorità

1. Descrivere **problema e impatto**: blocco completo/parziale, probabilità e frequenza, utenti e funzionalità coinvolti, workaround, rischio su rete, sicurezza e configurazioni.
2. Classificare: difetto WinNAT-UI; evento esterno correttamente/erroneamente gestito; configurazione/uso; miglioramento; duplicato; informazioni insufficienti.
3. Attribuire **una sola** priorità GitHub motivata:
   - `priority:P0`: incidente critico, perdita dati, impatto operativo o di sicurezza immediato e grave.
   - `priority:P1`: percorso essenziale non utilizzabile o rischio significativo di danni/configurazioni errate senza mitigazione praticabile.
   - `priority:P2`: difetto funzionale/affidabilità con impatto circoscritto o mitigazione; non è un valore di default automatico.
   - `priority:P3`: difetto minore di presentazione, testi o ergonomia.
4. Se mancano dati per valutarla, dichiarare «priorità da valutare» e chiedere prove mirate: non attribuire priorità sulla base del solo traceback.
5. Pubblicare il **commento strutturato** del § 5 e assegnare chiaramente il prossimo passo.

### C. Diagnosi tecnica e riproduzione

- Seguire il flusso end-to-end: pulsante/evento UI → funzione → modulo Python/PowerShell/servizio GitHub → eccezione/risposta → gestione e messaggio per l'utente.
- Esaminare il codice **della versione segnalata**, le differenze con main, PR/commit pertinenti e test. Separare osservazione del problema dalla causa dedotta.
- Cercare condizioni alternative (offline intenzionale, risoluzione DNS, TLS/proxy, timeout, risposta HTTP, permessi, configurazione rete). Wi-Fi attivo e route predefinita non dimostrano accesso Internet; un errore remoto non prova un errore NAT.
- Annotare esperimenti replicabili, risultati positivi/negativi, cause escluse e limiti dei test. Richiedere log o comandi minimi soltanto quando necessari, evitando nuove esposizioni di dati sensibili.
- Con diagnosi confermata applicare `triage:confermato`; se restano verifiche essenziali, usare `triage:informazioni-richieste` e specificare esattamente cosa serve. «Non riproducibile» si usa solo dopo prove adeguate documentate, non per assenza di informazioni.

### D. Piano, modifica e test

- Proporre soluzione con punto di modifica, comportamento desiderato, scenari limite, regressioni da evitare, dipendenze, impatto sui dati e rollback. Se l'intervento viene avviato, passare a `triage:in-correzione`.
- Collegare Issue ↔ PR ↔ commit correttivo. Applicare le regole AGENTS.md: review del diff, precedenza fra PR, test automatici, build Windows, Defender, versioning e controlli post-merge, secondo pertinenza.
- Non modificare automaticamente NAT, DNS, interfacce, routing o forwarding per gestire un semplice evento GitHub/offline non correlato.
- Registrare esplicitamente quali test **non** sono stati eseguiti (per esempio, prova reale con Windows scollegato); un CI verde non equivale al collaudo operativo.
- Non dichiarare «Risolto» e non chiudere solo perché una PR è stata integrata.

### E. Release risolutiva e chiusura

1. Identificare il commit effettivo del fix e la **prima release pubblica** che lo contiene; verificare l'ancestry tramite confronto GitHub commit → tag.
2. Controllare GitHub Release pubblicata, versione coerente, note e asset; non confondere `X.Y.Z+ci...`, main o tag non pubblicato con una release.
3. **Soltanto allora** applicare un'unica label `fixed-in/vX.Y.Z` (oppure `fixed-in/vX.Y.Z.H` per HOTFIX). Se manca la prova, lasciare la release da determinare, documentando il motivo.
4. Annotare in un commento PR, commit SHA, tag, link release, verifica eseguita e prova funzionale. Se manca il collaudo, mantenere `triage:correzione-disponibile`.
5. Dopo la verifica funzionale documentata (test reale o riscontro esplicito del segnalante), impostare `triage:risolto` e chiudere la Issue con ragione coerente (normalmente `completed`). Dichiarare eventuali scenari non collaudati senza sostenere che la prova copra tutto.
6. **Non cancellare la priorità** alla chiusura: resta parte della storia del bug.
7. Se il problema riappare, riaprire o creare una nuova Issue a seconda della causa dimostrata, collegando evidenze e versioni.

### F. Verifica obbligatoria del risultato in GitHub e nella UI

Dopo ogni cambio rilevante, rileggere la Issue GitHub per verificare:
- Titolo chiaro, ID/fingerprint integri, una sola `triage:*`, una sola `priority:*` quando deliberata.
- Nessuna label `fixed-in/*` prematura, multipla o riferita a una release che non contiene il fix.
- Stato `open/closed` coerente con triage e commento.
- Commento che illustri evidenze, ragioni della scelta, prossimo passo, responsabile e release (se nota).
- Da WinNAT-UI, **Informazioni → Bug segnalati → Verifica stato Issue**: titolo, stato, priorità e versione correttiva devono coincidere con GitHub. Verificare che il refresh sia riuscito **online**; in modalità offline può essere mostrato solo lo storico locale.
- Distinguere «Correzione prevista/risolutiva» da «Aggiornamento disponibile»: la seconda dipende anche da versione installata e ultima release rilevata.

Se dopo il refresh la UI mostra ancora «Da valutare» o «Da definire», **prima verificare le label sulla Issue**. In WinNAT-UI [issue_tracker.py](../winnat_ui/issue_tracker.py) legge le label; [app.py](../app.py) visualizza i fallback quando `priority` o `fixed_in` sono assenti. Se le label sono corrette, indagare sincronizzazione, connettività, versione app e associazione `number/fingerprint`; documentare eventualmente un nuovo bug senza confondere il problema applicativo con la Issue originaria.

## 3. Stati validi — una sola label di triage alla volta

| Label | Significato |
|---|---|
| `triage:ricevuto` | Report ricevuto, non ancora analizzato |
| `triage:in-analisi` | Analisi iniziale in corso |
| `triage:informazioni-richieste` | Dati o test mancanti specificamente richiesti |
| `triage:confermato` | Problema confermato da evidenze |
| `triage:in-correzione` | Soluzione in lavorazione |
| `triage:correzione-disponibile` | Fix pubblicato, conferma operativa ancora pendente |
| `triage:risolto` | Esito corretto verificato e documentato |
| `triage:duplicato` | Duplicazione dimostrata, Issue primaria collegata |
| `triage:non-riproducibile` | Riproduzione tentata, documentata e non riuscita |

Le label `bug-report`, `priority:*` e `fixed-in/v*` sono distinte dalla fase di triage. Non basta descrivere una transizione nei commenti: **aggiornare materialmente le label**.

## 4. Dati e fonti per l'app

| Campo UI | Fonte autorevole |
|---|---|
| Numero e associazione locale | ID Issue e fingerprint del report |
| Nome riconoscibile del problema | Titolo attuale GitHub |
| Stato aperto/chiuso | `state` GitHub |
| Stato del problema | Label `triage:*` |
| Priorità | Label `priority:P0` … `priority:P3` |
| Release risolutiva | Label `fixed-in/vX.Y.Z[.H]` |
| Evidenze/decisioni/PR | Commenti, commit, CI e release, **non** letti dalle colonne UI |
| Cronologia personale | Cache locale dell'app, preservata se GitHub irraggiungibile |

## 5. Schema minimo per ogni commento di analisi

Sostituire i campi senza inventare dati e senza ripubblicare l'intero traceback.

> **Triage / aggiornamento — [data UTC]**  
> **Issue:** #ID — titolo descrittivo  
> **Scenario, versione e impatto:** ...  
> **Categoria e priorità:** ... / Pn o da valutare (motivazione)  
> **Stato triage:** ...  
> **Evidenze confermate:** ...  
> **Ipotesi e diagnosi ancora da verificare:** ...  
> **Cause escluse e limiti dei test:** ...  
> **Intervento/workaround proposto o eseguito:** ...  
> **Responsabile e prossimo passo:** ...  
> **Informazioni richieste / test di accettazione:** ...  
> **PR/commit correttivi:** ... (solo se esistenti)  
> **Prima release pubblica contenente il fix:** ... (solo dopo verifica)  
> **Collaudo e risultato:** ... / non eseguito  
> **Label aggiornate:** ... (solo dopo applicazione e rilettura)

## 6. Checklist di accettazione del triage

- [ ] Segnalazione riconosciuta, correlazioni e duplicati verificati.
- [ ] Titolo specifico; causa confermata distinta da congetture.
- [ ] Impatto e priorità motivati, e **label priority** applicata se determinabile.
- [ ] Una sola **label triage** allineata all'attività realmente svolta.
- [ ] Riproduzione, codice, ambiente, test e limiti documentati.
- [ ] Commento con prossima azione, responsabile ed eventuali richieste.
- [ ] PR e commit citati soltanto se esistenti.
- [ ] Release risolutiva verificata e **label fixed-in** aggiornata quando pubblicata.
- [ ] Stato GitHub, commenti e metadati coerenti, anche dopo la chiusura.
- [ ] Eseguita rilettura GitHub e, quando possibile, sincronizzazione dalla UI online.
- [ ] Nessun segreto o inventario non necessario aggiunto ai commenti pubblici.

## 7. Caso di riferimento: Issue #65

L'utente aveva scollegato intenzionalmente il PC da Internet. L'operazione «Stato bug» generava un'eccezione `URLError/getaddrinfo failed` non gestita: il problema applicativo era **la gestione dell'evento esterno atteso**, non un guasto WinNAT. La correzione è stata integrata dalla [PR #69](https://github.com/matiz311/WinNAT-UI/pull/69), commit `3eb242657883c28a7bdf5c15a432c2ea2e506640`, contenuto nella [release pubblicata v1.16.0](https://github.com/matiz311/WinNAT-UI/releases/tag/v1.16.0).

Il segnalante ha confermato il rientro dell'anomalia. La Issue è stata chiusa con i metadati **`triage:risolto`, `priority:P2`, `fixed-in/v1.16.0`**, aggiunti dopo aver constatato che i soli commenti non comparivano come stato, priorità e release nell'app. Il riscontro non dimostra che ogni altra casistica remota (timeout, TLS, HTTP, ecc.) sia stata collaudata.

**Regola esemplificata:** diagnosi documentata + label aggiornate + release verificata + eventuale conferma utente + lettura finale della Issue. Questo è il ciclo standard, non una procedura eccezionale.
