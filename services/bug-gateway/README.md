# Servizio di segnalazione anonima (amministratore)

## Perché è necessario
GitHub non consente a un EXE anonimo di creare Issue senza autenticazione. Non
inserire un token GitHub nell'applicazione: sarebbe recuperabile e utilizzabile
da chiunque. Questo Cloudflare Worker funge da proxy con credenziali custodite
esclusivamente lato server. **Finché il Worker non è distribuito, il pulsante
Segnala bug non può creare Issue autonomamente.**

## Attivazione
1. Crea un account Cloudflare amministrato dal proprietario del repository.
2. Crea una KV namespace Cloudflare e sostituisci il placeholder nel file
   `wrangler.toml`. Aggiungi una regola WAF con rate limiting per `/report`;
   il limite KV del codice è solo una difesa best effort, non atomica.
3. Crea un token GitHub *fine-grained*, limitato **esclusivamente**
   al repository `matiz311/WinNAT-UI`, con permesso **Issues: Read and Write**.
   L'account che possiede il token diventerà l'autore tecnico delle Issue
   create dagli utenti anonimi.
4. Dal terminale di amministrazione usa:
   `npx wrangler secret put GITHUB_ISSUE_TOKEN`, incolla il token nel prompt
   senza salvarlo in file o nel repository; poi `npx wrangler deploy`.
5. Nel repository GitHub crea l'etichetta `bug-report`. A ogni correzione
   verificata, aggiungi alla relativa Issue l'etichetta
   `fixed-in/v1.9.7` (sostituendo la versione reale), e pubblica la release.
6. Prova il Worker con un report sintetico senza configurazioni reali.
   Verifica creazione, duplicati, rate limiting ed eventuali abusi.
7. Solo dopo aver verificato il backend, imposta in `bug-service.json`:
   `{"submit_url":"https://<worker>.<account>.workers.dev/report"}`
   e pubblica la modifica in `main`. Gli EXE già distribuiti
   leggeranno questo file dal repository ufficiale senza nuova build.

## Protezioni e limitazioni
- Il client invia **solo campi già anonimizzati** in una lista chiusa. Il
  Worker convalida di nuovo ogni campo; rifiuta JSON eccessivi, campi non
  previsti e valori sconosciuti.
- Il backend non ha accesso a informazioni di rete, log, hostnames o credenziali.
  Cloudflare può vedere l'IP sorgente per il funzionamento del rate limiting;
  non inserirlo nelle Issue né nei log applicativi.
- L'esposizione anonima può comunque essere sfruttata per spam. Attiva
  WAF, bot management e monitoraggio: il rate limit KV da solo non basta.
- I bug duplicati vengono raggruppati con un identificatore deterministico,
  basato su categoria, operazione, eccezione e moduli. Può accorpare problemi
  distinti oppure non riconoscere un duplicato.
- Il rilascio di una versione non implica automaticamente che un bug sia
  risolto: serve un'etichetta `fixed-in/vX.Y.Z` sulla Issue.
- Nessun deploy Cloudflare è incluso automaticamente nella CI GitHub: occorre
  prima autorizzare e configurare l'account cloud e la credenziale GitHub.
