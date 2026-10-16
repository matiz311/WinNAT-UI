## Obiettivo e modifiche sostanziali
<!-- Riassumere cosa cambia a livello funzionale, non soltanto l'elenco dei file. -->

## Impatto e compatibilità
<!-- Comportamento WinNAT/LAN/WAN, configurazioni, rollback, sicurezza, updater, packaging, versioni. -->

## Dipendenze e sovrapposizioni
<!-- Indicare PR/branch correlati, file o percorsi logici comuni, incompatibilità architetturali e piano di integrazione. Scrivere "nessuna rilevata" solo dopo il controllo. -->

## Provenienza e ordine di integrazione
- Autore effettivo della modifica: <!-- ChatGPT / Claude; non necessariamente chi ha aperto la PR -->
- Data originale della richiesta/PR (UTC): <!-- Non la data dell'ultimo commit -->
- Importanza motivata: <!-- Critical / High / Normal / Low -->
- Dipendenze o ostacoli all'ordine previsto: <!-- ChatGPT prima di Claude; poi importanza e data crescente -->

## Verifica versioning (per ogni PR)
- Classificazione proposta: <!-- MAJOR / MINOR / PATCH / HOTFIX / BUILD-only, senza bump -->
- Versione corrente su `main` e ultima GitHub Release:
- File di versione/changelog/release note da allineare, se necessari:
- Collisioni con versioning o changelog di altre PR:

## Test e build
- [ ] Test pertinenti eseguiti, con risultati indicati sotto
- [ ] CI Windows sull'ultima versione della PR: test, PyInstaller, metadati EXE e Defender verificati
- [ ] Limitazioni e test Windows reali ancora necessari esplicitati

Risultati / link alle esecuzioni:

## Riservato a ChatGPT — gate di integrazione
- [ ] Provenienza verificata e coda ordinata: prima ChatGPT, poi Claude; per importanza e successivamente per data originale crescente
- [ ] Versioning di tutte le PR verificato, inclusi bump concorrenti, versioni già pubblicate e coerenza con la release
- [ ] Versione finale dell'integrazione decisa una sola volta e motivata (anche se invariata)
- [ ] Diff e modifiche sostanziali riesaminati
- [ ] PR aperte e modifiche recenti confrontate, incluse sovrapposizioni semantiche
- [ ] Modifiche correlate riconciliate su un candidato integrato coerente
- [ ] Build/CI positiva sul candidato finale e SHA verificato
- [ ] Merge eseguito esclusivamente da ChatGPT
- [ ] Build post-merge su `main` verificata e artifact controllato

**Claude non può effettuare merge né abilitare auto-merge. La PR resta aperta fino all'integrazione da parte di ChatGPT.**
