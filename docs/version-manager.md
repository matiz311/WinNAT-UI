# Gestione versioni e diagnostica WinNAT-UI

## Navigazione
- **Diagnostica**: acquisizione locale in sola lettura mediante `network.collect`; visualizzazione, copia o esportazione JSON. Informazioni di rete e topologia non vengono inviate automaticamente a GitHub.
- **Aggiornamenti**: selezione del canale **Release ufficiali / rollback** oppure **Build di test CI**. I dati arrivano dalle API pubbliche della repository ufficiale, non da repository o URL scelti dall'utente.

## Release ufficiali
Il catalogo mostra fino a 50 release pubblicate, escludendo draft e prerelease. Un asset Windows è disponibile solo quando nome, URL esatto, digest SHA256 e dimensione sono validi. Qualsiasi release precedente può essere selezionata per reinstallazione/downgrade. Lo staging, il backup della directory e il ripristino automatico in caso di errore utilizzano il helper di `winnat_ui/updater.py`, senza modificare WinNAT o il routing. Il rollback della directory dei programmi **non è** un rollback della configurazione del sistema operativo, né garantisce la compatibilità dei dati locali creati da versioni successive.

## Build CI non ufficiali
Un identificativo `X.Y.Z+ci.<run_number>.<commit_prefix>` distingue le compilazioni della stessa versione funzionale senza produrre tag Git o nuove release. Il catalogo elenca fino a 12 build che:
1. appartengono al workflow `.github/workflows/build.yml` e alla repository ufficiale;
2. risultano concluse con successo in GitHub Actions;
3. contengono un artifact Windows ancora disponibile, non scaduto;
4. forniscono digest SHA256, dimensione e URL GitHub Actions esatti.

La UI indica chiaramente **Build di test CI (non ufficiali)**, run, commit, branch e scadenza. Sono comprese anche build da PR, che possono introdurre comportamenti non ancora revisionati o integrati; l'installazione richiede una conferma esplicita. Le build scadono con la retention configurata su GitHub: non sono archivi permanenti.

GitHub richiede credenziali per il **download degli Actions artifact**. L'app tenta di usare una sessione `gh auth login` già presente; in alternativa richiede un token temporaneo con permesso **Actions: read**. Il token rimane esclusivamente in memoria per l'operazione corrente: non viene scritto su file, nei log o nell'eseguibile; la richiesta autenticata va solo all'API GitHub. Il redirect di download viene controllato e viene seguito senza Authorization. Per chi non vuole autenticarsi, le release pubblicate restano scaricabili e installabili senza token.

Lo staging della build verifica l'hash dell'intero artifact, l'EXE, `SHA256.txt`, `DEFENDER_SCAN.txt` e `BUILD_INFO.txt`; commit, run e identificativo CI devono essere coerenti con la build selezionata. Questi controlli **non trasformano una build CI in una release verificata su host reale** e non equivalgono a una firma Authenticode. Il file `BUILD_INFO.txt` è presente anche nelle release pubbliche, quindi la sua presenza da sola non stabilisce che l'installazione provenga da un canale non ufficiale.

## Compatibilità, autorizzazioni e limitazioni
- Installazione/downgrade richiedono la versione compilata EXE Windows; la UI lancia l'helper solo dopo la verifica e la conferma, attendendo il segnale di apertura della sua finestra.
- Se una modifica WinNAT è preparata o vi sono task attivi, l'installazione è bloccata.
- Per la diagnostica VPN comparativa A/B/C in lavorazione nella PR #80 si dovrà coordinare un'integrazione delle interfacce; nessuna modifica a VPN, WinNAT o strumenti di diagnostica della PR #80 è inclusa qui.
- Per la gestione manuale delle Issue della PR #81, il nuovo catalogo non altera API e storage dei bug.
- Versione funzionale invariata in questa PR (BUILD-only nello staging di sviluppo); eventuale release MINOR successiva segue l'approvazione esplicita di `VERSIONING_POLICY.md`.
- Sono necessari build e test su GitHub Actions, oltre al collaudo interattivo su Windows 10/11 per download di artifact, finestra di installazione, downgrade e rollback.
