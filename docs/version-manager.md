# Gestione versioni e diagnostica WinNAT-UI

## Navigazione
- **Diagnostica**: acquisizione locale in sola lettura mediante `network.collect`; visualizzazione, copia o esportazione JSON. Informazioni di rete e topologia non vengono inviate automaticamente a GitHub.
- **Aggiornamenti**: selezione del canale **Release ufficiali / rollback** oppure **Build di test CI**. I dati arrivano dalle API pubbliche della repository ufficiale, non da repository o URL scelti dall'utente.

## Release ufficiali
Il catalogo mostra fino a 50 release pubblicate, escludendo draft e prerelease. Un asset Windows è disponibile solo quando nome, URL esatto, digest SHA256 e dimensione sono validi. Qualsiasi release precedente può essere selezionata per reinstallazione/downgrade. Lo staging, il backup della directory e il ripristino automatico in caso di errore utilizzano il helper di `winnat_ui/updater.py`, senza modificare WinNAT o il routing. Il rollback della directory dei programmi **non è** un rollback della configurazione del sistema operativo, né garantisce la compatibilità dei dati locali creati da versioni successive.

## Build CI sperimentali senza autenticazione
Il canale separato delle preview è composto da:
1. il branch tecnico **\`ci-builds\`**, creato senza cronologia applicativa come branch *orphan*, contenente soltanto \`index.json\` (ultime 12 build);
2. **GitHub pre-release** con tag tecnici \`ci-run-<run_id>\`, asset \`WinNAT-UI-Windows.zip\` scaricabili pubblicamente senza PAT o \`gh auth\`. Non sono release funzionali \`vX.Y.Z\` e non possono sostituire \`releases/latest\`;
3. un workflow \`publish-ci-preview.yml\`, attivo soltanto dopo il merge in \`main\`, avviato dal completamento con esito **success** di \`Build Windows executable\` e con \`GITHUB_TOKEN\` \`actions:read/contents:write\`.

Il publisher esegue esclusivamente il codice del branch \`main\`, mai i sorgenti o script della PR da cui proviene il pacchetto. Sono escluse le PR di fork. Prima della pubblicazione verifica origine/workflow/run, corrispondenza artifact, dimensione/hash ZIP, presenza degli esiti Defender e checksum dell'EXE, versione e commit in \`BUILD_INFO.txt\`. Il pacchetto Windows non viene eseguito dal publisher.

La UI scarica l'indice dal solo URL fisso \`raw.githubusercontent.com/matiz311/WinNAT-UI/ci-builds/index.json\`. **Ogni record deve corrispondere ad una pre-release effettiva nell'API GitHub**, con tag, commit sorgente, URL completo asset, dimensione e digest SHA-256 identici. Dopo il download tramite URL pubblico, il file viene verificato e preparato tramite gli stessi controlli già usati per le build CI, quindi installato solo dopo consenso dell'utente. Non viene mai richiesto un token.

L'identificativo interno rimane \`X.Y.Z+ci.<run_number>.<build_sha8>\`; il tag \`ci-run-<run_id>\` è soltanto un identificatore di distribuzione sperimentale, **non** una versione funzionale o ufficiale. Sono consultabili anche le build di PR interne non ancora revisionate: l'utente deve considerarle potenzialmente meno affidabili. L'esito positivo CI e Defender non equivalgono a firma Authenticode o collaudo sull'host.

**Limiti e gestione:** \`ci-builds\` non viene scritto nella cronologia di \`main\`; i ZIP non sono versionati in Git. L'indice mantiene le 12 build più recenti, mentre le vecchie pre-release pubblicate restano archiviate (l'eventuale eliminazione futura richiede una politica di retention separata). Se il branch non esiste ancora la UI mostra zero build senza interrompere le release stabili. Il workflow può pubblicare solo quando esiste su \`main\`, quindi una PR verde non rende già disponibile il nuovo catalogo. Per eventuali errori \`Resource not accessible by integration\` verificare in GitHub → Settings → Actions → General che i workflow autorizzati possano ottenere \`contents:write\`: nessuna nuova app esterna è necessaria.

## Compatibilità, autorizzazioni e limitazioni
- Installazione/downgrade richiedono la versione compilata EXE Windows; la UI lancia l'helper solo dopo la verifica e la conferma, attendendo il segnale di apertura della sua finestra.
- Se una modifica WinNAT è preparata o vi sono task attivi, l'installazione è bloccata.
- Per la diagnostica VPN comparativa A/B/C in lavorazione nella PR #80 si dovrà coordinare un'integrazione delle interfacce; nessuna modifica a VPN, WinNAT o strumenti di diagnostica della PR #80 è inclusa qui.
- Per la gestione manuale delle Issue della PR #81, il nuovo catalogo non altera API e storage dei bug.
- Versione funzionale invariata in questa PR (BUILD-only nello staging di sviluppo); eventuale release MINOR successiva segue l'approvazione esplicita di `VERSIONING_POLICY.md`.
- Sono necessari build e test su GitHub Actions, oltre al collaudo interattivo su Windows 10/11 per download di artifact, finestra di installazione, downgrade e rollback.
