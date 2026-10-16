# Versioning e pubblicazione — WinNAT-UI

**Ramo di manutenzione:** la release v1.14.1 deriva direttamente dal tag v1.14.0 e include esclusivamente correzioni dell'updater. Il ramo main prepara invece la MINOR 1.15.0. Le due linee devono avere tag, build e metadati Windows separati.

## Fonte della versione
La versione funzionale è `MAJOR.MINOR.PATCH[.HOTFIX]`; il quarto componente è una **estensione del progetto**, riservata agli interventi urgenti. La fonte è `version.py`. La versione dell'eseguibile Windows in `version_info.txt`, il tag Git `vX.Y.Z[.H]`, il nome della release e i metadati dell'updater devono coincidere. Nelle proprietà Windows le versioni a tre componenti mostrano il quarto componente numerico zero.

La build CI ha un identificatore indipendente `X.Y.Z[.H]+ci.<run>.<sha>` scritto in `BUILD_INFO.txt` e non genera una nuova versione funzionale.

## Classificazione
| Classe | Incremento | Uso |
|---|---|---|
| MAJOR | `2.0.0` | Incompatibilità intenzionali e migrazioni |
| MINOR | `1.14.0` | Nuove capacità rilevanti e retrocompatibili |
| PATCH | `1.14.1` | Manutenzione del controllo aggiornamenti, dalla base stabile 1.14.0 |
| HOTFIX | `1.14.0.1` | Correzione urgente della release già pubblicata |
| BUILD | `1.14.0+ci.209.abcd1234` | Ricompilazione senza nuove funzionalità |

Progressione corretta: `1.13.0` → `1.13.0.1` → `1.13.1` → `1.14.0`.
Un HOTFIX deve incorporare il fix nell'aggiornamento PATCH o MINOR successivo; il quarto componente torna a zero. Non creare un quarto numero per una build ripetuta.

## Procedura di rilascio
1. Aggiornare `version.py` e `version_info.txt`, verificare che le due rappresentazioni coincidano.
2. Aggiungere la sezione `## [X.Y.Z]` nel `CHANGELOG.md`. MINOR e MAJOR richiedono obbligatoriamente `### Sintesi`, `### Funzionalità` e `### Correzioni` con informazioni verificabili.
3. Aggiornare `RELEASE_NOTES.it.md` con novità, correzioni, compatibilità, limitazioni e collegamento alle Issue aperte.
4. Eseguire test unitari e build Windows, validare versione EXE, scansione Defender, integrità ZIP e digest GitHub.
5. Per MINOR e MAJOR utilizzare l'approvazione esplicita in GitHub Actions. Non pubblicare automaticamente un avanzamento funzionale a ogni commit.
6. Non sovrascrivere tag/asset già pubblicati; la migrazione dello storico è una procedura eccezionale e tracciata separatamente.
7. Eseguire un test reale dell'updater prima di dichiarare stabilità dell'aggiornamento sul campo.

## Migrazione storica approvata nel 2026
I seguenti identificativi provengono dalle 28 release effettivamente pubblicate il 14–15 ottobre 2026. Ogni nuovo tag deve puntare a un sorgente riprodotto con versione interna aggiornata, non a un tag alias arbitrario. Le build storiche vengono prima conservate e verificate in staging.

| Tag precedente | Tag rinumerato |
|---|---|
| `v1.2.0` | `v1.2.0` |
| `v1.3.0` | `v1.3.0` |
| `v1.4.0` | `v1.4.0` |
| `v1.6.0` | `v1.5.0` |
| `v1.6.1` | `v1.5.1` |
| `v1.7.0` | `v1.5.2` |
| `v1.7.1` | `v1.6.0` |
| `v1.7.2` | `v1.6.1` |
| `v1.7.3` | `v1.6.2` |
| `v1.7.4` | `v1.6.3` |
| `v1.7.5` | `v1.6.4` |
| `v1.8.0` | `v1.7.0` |
| `v1.9.0` | `v1.8.0` |
| `v1.9.2` | `v1.9.0` |
| `v1.9.3` | `v1.10.0` |
| `v1.9.4` | `v1.10.1` |
| `v1.9.5` | `v1.10.2` |
| `v1.9.6` | `v1.11.0` |
| `v1.9.7` | `v1.11.1` |
| `v1.9.8` | `v1.11.2` |
| `v1.9.9` | `v1.12.0` |
| `v1.9.10` | `v1.12.1` |
| `v1.9.11` | `v1.12.2` |
| `v1.9.12` | `v1.12.3` |
| `v1.9.13` | `v1.12.4` |
| `v1.9.14` | `v1.12.5` |
| `v1.9.15` | `v1.13.0` |
| `v1.9.15.1` | `v1.13.0.1` |

`v1.9.1` non aveva più un tag o una release al momento dell'inventario, quindi le funzionalità allora documentate sono incorporate nel primo rilascio verificabile `v1.9.0` (precedentemente `v1.9.2`). `v1.10.0` era il numero del sorgente aggiornato, **non una release pubblicata**: la sua nuova prima release è `v1.14.0`. Il vecchio `v1.10.1` errato era già stato ritirato e non fa parte delle 28 release reali.

Le note destinate agli utenti sono in [RELEASE_NOTES.it.md](RELEASE_NOTES.it.md); il dettaglio in [CHANGELOG.md](CHANGELOG.md). Le Issue aperte sono consultabili in https://github.com/matiz311/WinNAT-UI/issues?q=is%3Aissue+is%3Aopen .

## Identificazione e integrità
`BUILD_INFO.txt` contiene versione, identificativo della build, commit e workflow. Ogni asset ZIP pubblicato deve avere un digest SHA-256 verificabile. La presenza di una scansione Defender non equivale a una firma digitale: indicare sempre lo stato effettivo della firma nelle release notes.
