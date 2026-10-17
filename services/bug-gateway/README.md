# Backend segnalazioni diagnostiche WinNAT-UI

L'applicazione invia **solo dopo esplicita conferma** report dettagliati a Cloudflare Workers. Il report può comprendere errore originale, traceback Python, script e output PowerShell, ambiente, IP e topologia di rete e modifiche in sospeso. Password, token, email e identificativi nei percorsi sono oscurati dove riconoscibili, senza garantire una sanitizzazione perfetta. **Le Issue GitHub sono pubbliche**: l'utente può leggere e copiare il report prima della pubblicazione. Il Worker applica una seconda sanitizzazione, valida ogni campo, limita l'abuso e crea una GitHub Issue etichettata `bug-report` nel repository `matiz311/WinNAT-UI`, oppure commenta la Issue già aperta aggiungendo le nuove evidenze. Nessun token GitHub è incluso nell'eseguibile.

## Prima attivazione (Cloudflare + GitHub Actions)

1. Crea o utilizza un [account Cloudflare](https://dash.cloudflare.com/) con sottodominio `workers.dev` disponibile.
2. In [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) crea un token dedicato, limitato al tuo account, con permessi di deploy/modifica Workers. [Guida ufficiale](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/).
3. Recupera l'**Account ID** nella dashboard Cloudflare.
4. Crea un [GitHub fine-grained PAT](https://github.com/settings/personal-access-tokens), limitato al solo repository `matiz311/WinNAT-UI`, con permesso **Issues: Read and write**. L'autore tecnico delle Issue sarà l'account che possiede questo token: i segnalatori resteranno anonimi rispetto al maintainer.
5. In **WinNAT-UI → Settings → Secrets and variables → Actions → Repository secrets**, configura:
   - `CLOUDFLARE_API_TOKEN`: token Cloudflare per il deploy.
   - `CLOUDFLARE_ACCOUNT_ID`: identificatore dell'account Cloudflare.
   - `WINNAT_ISSUE_TOKEN`: GitHub PAT limitato alle Issue.
6. Avvia **Actions → Deploy anonymous issue gateway → Run workflow**, oppure integra le modifiche in `main` con i secret già impostati.

Il workflow verifica i test Node, distribuisce il Worker, pubblica il PAT come **secret lato Cloudflare**, verifica `GET /health`, crea la label `bug-report` e aggiorna `bug-service.json` con l'endpoint effettivo `https://...workers.dev/report`. Il client WinNAT-UI usa la configurazione GitHub senza una nuova build. Il workflow richiede i permessi `contents:write` e `issues:write` tramite `GITHUB_TOKEN` per aggiornare il file e creare la label; eventuali regole di protezione sul branch possono impedirne l'aggiornamento automatico.

**Non condividere né pubblicare i token** nel codice, nella chat, nei log, nelle Issue o nell'app desktop. Per sicurezza l'endpoint rimane `null` in `bug-service.json` fino a quando il deploy e la verifica /health non hanno avuto esito positivo.

## Verifica dopo il deploy

- `GET https://<worker>.<account>.workers.dev/health` deve restituire `{"status":"ready"}`.
- Lancia un report di **prova** dal client con dati non riservati e verifica la creazione di una GitHub Issue etichettata `bug-report`.
- Invia di nuovo lo stesso report per controllare la deduplicazione e verificare che appaia un nuovo commento con le evidenze.
- L'health check da solo **non** garantisce che il token GitHub abbia permessi di creazione Issue: serve un invio reale.

## Diagnostica manuale e aggiornamento di Issue esistenti (PR #80)

Il client aggiornato espone **Panoramica → Diagnostica e OpenIssue** e **Informazioni → Apri centro diagnostico**. L'utente può avviare una raccolta generica in sola lettura (adattatori, routing, indirizzi, WinNAT, DNS, servizi pertinenti), scrivere una descrizione senza necessità di un errore Python, revisionare e modificare l'intero Markdown, ed esportarlo o copiarlo **senza inviarlo**.

Dopo conferma esplicita il client invia `POST /report` con payload `mode: "manual"`, `title`, `category`, `body`, `version` e `issue_number` (null per una nuova Issue). Il Worker conserva il vecchio contratto per gli errori automatici, che continuano a essere deduplicati.

- **Nuova Issue:** crea una segnalazione distinta etichettata `bug-report` e `triage:ricevuto`, con un fingerprint per la sincronizzazione del client. Le nuove segnalazioni manuali **non sono deduplicate automaticamente**: la scelta di creare un nuovo caso è intenzionale.
- **Aggiornamento:** cerca esclusivamente nel repository ufficiale il numero di Issue indicato. Consente un commento solo se la Issue è **aperta**, non è una PR e ha già una label `bug-report` o `triage:*`. Per Issue chiuse, PR o discussioni prive di classificazione restituisce HTTP 409. Non permette modifiche al titolo, alle label, allo stato o ad altri repository.
- **Segui Issue:** permette di importare una Issue GitHub già esistente nell'elenco locale, anche senza fingerprint originato dall'app, e ne legge i metadati tramite API pubblica. L'importazione non pubblica dati.
- **Sicurezza:** dimensione massima del corpo manuale 24000 caratteri (oltre al limite JSON di 65536 byte), validazione stretta e sanitizzazione di segreti riconoscibili, rate limiting esistente e preview modificabile **prima** dell'invio. Il client può contenere IP/route ed è responsabilità dell'utente revisionare il report destinato a una Issue pubblica.

**Compatibilità/deployment:** la nuova operazione manuale richiede sia un client compilato con la PR sia il Worker aggiornato e distribuito. Una build di PR, da sola, **non** modifica il servizio Worker attualmente attivo. Fino al deploy l'utente può comunque raccogliere, copiare ed esportare il report e pubblicarlo manualmente da GitHub.

## Protezioni e limiti

- Payload JSON al massimo 65536 byte. I campi diagnostici includono categoria, operazione, eccezione, moduli, versione, exit code, firma dell'errore, sintesi, messaggio, traceback, ambiente e inventario. Lunghezze massime controllate per campo, rigetto dei campi inattesi e sanitizzazione di segreti riconoscibili sul client e sul gateway. La topologia e gli indirizzi IP vengono mantenuti.
- Rate limiting integrato in Cloudflare Workers: **6/minuto per IP sorgente** e **30/minuto per location Cloudflare** in totale, senza necessità di configurare KV. Gli IP servono a calcolare chiavi hash a runtime, non sono memorizzati nel report o nelle Issue. Più utenti sotto NAT condividono il limite per-IP.
- I limiti rate non sono globali né strettamente atomici: Cloudflare applica contatori per location, eventualmente consistenti. Per contrastare abusi consistenti configurare protezioni aggiuntive.
- La deduplicazione controlla al massimo 100 Issue aperte più recenti con label `bug-report`, usando categoria, operazione, eccezione, moduli e firma del messaggio d'errore nei nuovi client. Un duplicato aggiunge sempre un commento con un nuovo report completo, senza perdere le evidenze. Issue più vecchie o chiuse non sono necessariamente riutilizzate.
- Per segnalare la correzione applica una label `fixed-in/vMAJOR.MINOR.PATCH` alla Issue interessata. **Limite attuale:** il tracciamento delle correzioni riconosce soltanto label a tre componenti; una versione HOTFIX a quattro componenti non è ancora riconosciuta da questa funzione.
- Cloudflare può trattare l'IP pubblico della connessione per fornire il servizio e il rate limiting. Il maintainer non riceve l'IP tramite il contenuto della Issue.

## Test

Esegui `npm test` dalla cartella `services/bug-gateway` con Node.js 22+. I test usano risposte GitHub simulate: non consumano credenziali e non creano Issue reali.
