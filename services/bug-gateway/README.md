# Backend per segnalazioni anonime WinNAT-UI

L'applicazione invia volontariamente **solo campi diagnostici anonimizzati e predefiniti** a Cloudflare Workers. Il Worker valida ogni campo, limita l'abuso e apre (o riutilizza) una GitHub Issue `bug-report` nel repository `matiz311/WinNAT-UI`. Nessun token GitHub è incluso nell'eseguibile.

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
- Invia di nuovo lo stesso report per controllare la deduplicazione.
- L'health check da solo **non** garantisce che il token GitHub abbia permessi di creazione Issue: serve un invio reale.

## Protezioni e limiti

- Payload JSON al massimo 4096 byte: categoria, operazione, tipo eccezione, moduli in lista chiusa, versione, codice di uscita. Sono rifiutati campi arbitrari, log grezzi e configurazioni di rete.
- Rate limiting integrato in Cloudflare Workers: **6/minuto per IP sorgente** e **30/minuto per location Cloudflare** in totale, senza necessità di configurare KV. Gli IP servono a calcolare chiavi hash a runtime, non sono memorizzati nel report o nelle Issue. Più utenti sotto NAT condividono il limite per-IP.
- I limiti rate non sono globali né strettamente atomici: Cloudflare applica contatori per location, eventualmente consistenti. Per contrastare abusi consistenti configurare protezioni aggiuntive.
- La deduplicazione controlla al massimo 100 Issue aperte più recenti con label `bug-report`, usando un fingerprint basato su categoria, operazione, eccezione e moduli. Issue più vecchie o chiuse non sono necessariamente riutilizzate.
- Per segnalare la correzione applica `fixed-in/vMAJOR.MINOR.PATCH` alla Issue interessata.
- Cloudflare può trattare l'IP pubblico della connessione per fornire il servizio e il rate limiting. Il maintainer non riceve l'IP tramite il contenuto della Issue.

## Test

Esegui `npm test` dalla cartella `services/bug-gateway` con Node.js 22+. I test usano risposte GitHub simulate: non consumano credenziali e non creano Issue reali.
