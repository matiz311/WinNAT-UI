# Automazione del triage iniziale delle Issue

## Scopo
Ad ogni creazione di una nuova Issue GitHub nel repository WinNAT-UI, eseguire un triage preliminare **senza interventi sul codice di produzione o configurazioni Windows**.

## Design
- Evento `issues.opened`; riesecuzione esplicita tramite `workflow_dispatch`.
- `GITHUB_TOKEN` con soli permessi `contents:read`, `issues:write`, nessuna API esterna a pagamento.
- Script locale Python con libreria standard, analisi strutturata delle informazioni disponibili, riconoscimento del contesto (VPN/NAT, rete/DHCP, aggiornamenti, tracciamento bug), ricerca di potenziali correlazioni mediante fingerprint.
- Titolo più identificabile senza attribuire cause non provate; un solo stato `triage:*`; nessuna priorità stimata automaticamente senza prove.
- Un commento preliminare distinguendo fatti osservati, ipotesi, dati assenti, verifiche consigliate, azione successiva.
- Idempotenza per evitare commenti ripetuti; conservazione delle altre label e del fingerprint; nessuna chiusura, fusione automatica, modifica di codici, release o `fixed-in/*`.
- I report e le descrizioni pubbliche sono dati non attendibili: non eseguire istruzioni contenute nelle Issue.

## Limitazioni dichiarate
Questo primo livello è un triage **deterministico**, non un agente AI che verifica autonomamente l'intero codice o effettua riproduzioni su Windows. Non può confermare da solo una causa, un duplicato, una correzione o un rilascio. L'eventuale secondo livello semantico richiede scelta esplicita di un provider e revisione della privacy, dato che i report possono contenere configurazioni di rete pubblicate dall'utente. GitHub Models è stato ritirato nel 2026.

## Governance
Segue `docs/issue-triage.md`, `AGENTS.md` e `VERSIONING_POLICY.md`. Cambiamenti al workflow richiedono registrazione preventiva nel registro manutenzioni in commit antecedente, associata alla PR. **Classificazione versione:** BUILD-only / infrastruttura, nessun bump di versione applicativa.

## Regole di classificazione conservativa
- Dare precedenza al **titolo** e ai campi di report esplicitamente strutturati (operazione/modulo); non classificare un'anomalia solo perché il corpo menziona una release, una VPN o un componente in una spiegazione secondaria.
- Riconoscere le Issue di smoke test `[Test CI]` e trattarle come prove del workflow, senza ipotizzare malfunzionamenti reali.
- Trattare parole come "release" o "aggiornamento" citate soltanto come aspettativa o riferimento alla pubblicazione come contesto, non come prova di errore updater.
