# Segnalazione manuale e tracciamento Issue GitHub

## Dal software senza errore applicativo

Nella pagina **Informazioni → Bug segnalati e correzioni** selezionare
**Nuova segnalazione**. Inserire un titolo descrittivo (max 120 caratteri),
il tipo di problema e una descrizione con comportamento osservato,
condizioni e risultato atteso (max 8.000 caratteri). Il processo non
richiede alcuna eccezione Python né un errore interno WinNAT-UI.

La bozza riutilizza il payload JSON compatibile con il gateway Cloudflare
già distribuito: `operation=Segnalazione manuale`, nessun traceback,
messaggio introdotto dall'utente, versione e informazioni generali
sull'ambiente. L'inventario di rete è **disattivato per impostazione
predefinita** e viene incluso soltanto selezionando l'opzione dedicata.
La schermata permette la revisione dell'anteprima prima della conferma.

Il gateway conserva il comportamento attuale: ogni nuovo report crea
una Issue GitHub pubblica `bug-report`, oppure aggiunge evidenze a una
Issue aperta con lo stesso fingerprint. L'etichetta iniziale
`triage:ricevuto` deve essere successivamente aggiornata secondo
[issue-triage.md](issue-triage.md). I report manuali vengono inizialmente
classificati dal gateway nella categoria di fallback
`Errore operativo non classificato`: questo non indica che sia stata
generata un'eccezione nell'app. Dopo il triage assegnare un titolo e
una classificazione più accurati su GitHub.

## Collegare una Issue GitHub già esistente

Selezionare **Segui Issue GitHub** e incollare il numero (es. `#76`)
oppure il link `https://github.com/matiz311/WinNAT-UI/issues/76`.
Vengono accettate solo Issue effettive del repository ufficiale:
le pull request e gli URL esterni sono rifiutati.

La lista non viene importata integralmente: il collegamento è esplicito,
persistente nel file locale `reported-issues.json`, senza duplicare
Issue già seguite. **Verifica stato Issue** rilegge tramite le API
pubbliche numero, titolo, stato open/closed, timestamp, conteggio commenti
e label `triage:*`, `priority:*`, `fixed-in/v*`.
La sincronizzazione funziona anche per le Issue senza label
`bug-report` o fingerprint. Eventuali errori di rete non cancellano
i dati salvati localmente.

Per rispondere o allegare nuove informazioni, selezionare la Issue e
premere **Aggiungi informazioni su GitHub**: si apre la conversazione
nel browser, dove GitHub gestisce l'autenticazione. L'eseguibile non
contiene token né invia commenti a nome di altri utenti.

## Limiti

- I dati salvati sono locali alla specifica installazione Windows.
- La sincronizzazione è su richiesta (o al caricamento programmato della
  sezione) e non costituisce una notifica push in tempo reale.
- Solo Issue del repository ufficiale sono collegabili.
- I commenti vengono pubblicati dal browser GitHub, non dal client.
- La pubblicazione di segnalazioni manuali richiede un gateway
  funzionante, come per i report automatici; in caso di errore mostra
  un avviso senza generare un ulteriore report diagnostico.
