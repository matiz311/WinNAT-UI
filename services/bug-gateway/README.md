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

## Protezioni e limiti

- Payload JSON al massimo 65536 byte. I campi diagnostici includono categoria, operazione, eccezione, moduli, versione, exit code, firma dell'errore, sintesi, messaggio, traceback, ambiente e inventario. Lunghezze massime controllate per campo, rigetto dei campi inattesi e sanitizzazione di segreti riconoscibili sul client e sul gateway. La topologia e gli indirizzi IP vengono mantenuti.
- Rate limiting integrato in Cloudflare Workers: **6/minuto per IP sorgente** e **30/minuto per location Cloudflare** in totale, senza necessità di configurare KV. Gli IP servono a calcolare chiavi hash a runtime, non sono memorizzati nel report o nelle Issue. Più utenti sotto NAT condividono il limite per-IP.
- I limiti rate non sono globali né strettamente atomici: Cloudflare applica contatori per location, eventualmente consistenti. Per contrastare abusi consistenti configurare protezioni aggiuntive.
- La deduplicazione controlla al massimo 100 Issue aperte più recenti con label `bug-report`, usando categoria, operazione, eccezione, moduli e firma del messaggio d'errore nei nuovi client. Un duplicato aggiunge sempre un commento con un nuovo report completo, senza perdere le evidenze. Issue più vecchie o chiuse non sono necessariamente riutilizzate.
- Per segnalare la correzione applica una label `fixed-in/vMAJOR.MINOR.PATCH` alla Issue interessata. **Limite attuale:** il tracciamento delle correzioni riconosce soltanto label a tre componenti; una versione HOTFIX a quattro componenti non è ancora riconosciuta da questa funzione.
- Cloudflare può trattare l'IP pubblico della connessione per fornire il servizio e il rate limiting. Il maintainer non riceve l'IP tramite il contenuto della Issue.

## Test

Esegui `npm test` dalla cartella `services/bug-gateway` con Node.js 22+. I test usano risposte GitHub simulate: non consumano credenziali e non creano Issue reali.
