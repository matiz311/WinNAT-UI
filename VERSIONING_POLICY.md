# Versioning e pubblicazione — WinNAT-UI

## Stato attuale — 16 ottobre 2026

La **versione stabile pubblicata è `v1.15.0`**: [GitHub Releases](https://github.com/matiz311/WinNAT-UI/releases/latest). Il catalogo comprende **31 release pubbliche**: le 28 precedenti sono state ricompilate e rinumerate il 16 ottobre 2026, seguite da `v1.14.0`, dalla PATCH `v1.14.1` e dalla MINOR `v1.15.0`. L'ultimo HOTFIX precedente è **`v1.13.0.1`**. I tag e i numeri usati nei documenti sono quelli attualmente pubblicati; gli identificativi dismessi non sono alias di download.

Le informazioni complete di ogni rilascio si trovano in [CHANGELOG.md](CHANGELOG.md) e [RELEASE_NOTES.it.md](RELEASE_NOTES.it.md). La sequenza effettiva più recente è `v1.13.0` → `v1.13.0.1` → `v1.14.0` → `v1.14.1` → `v1.15.0`.

**Rilascio MINOR 1.15.0:** incorpora le correzioni della v1.14.1 e le funzionalità e integrazioni delle PR #54, #55/#60, #56, #57, #59 e #58. Per questo solo rilascio, il proprietario del repository ha autorizzato espressamente ChatGPT ad avviare la pubblicazione in autonomia il 16 ottobre 2026. L'autorizzazione è tracciata in `release-approvals/v1.15.0.md`; il workflow la riconosce una sola volta, soltanto se la versione, il commit di base e i file modificati coincidono con quelli previsti, senza disattivare build/test, scansione Defender, controlli di sicurezza né il gate di versione. Dalle release successive rimane obbligatorio il normale `workflow_dispatch` approvato.

## Fonte della versione

La versione funzionale segue `MAJOR.MINOR.PATCH[.HOTFIX]`. Il quarto componente è una **estensione specifica del progetto**, non parte del SemVer 2.0.0 puro. La fonte è `version.py`; la versione nelle risorse Windows (`version_info.txt`), il tag Git `vX.Y.Z[.H]`, la GitHub Release e i metadati dell'updater devono coincidere. Windows rappresenta una versione con tre componenti come `X.Y.Z.0`.

L'identificativo di una **build CI** è distinto dalla versione funzionale: `X.Y.Z[.H]+ci.<run>.<sha>` in `BUILD_INFO.txt`. Non è un tag Git e non crea automaticamente una nuova release.

## Classificazione degli incrementi

| Categoria | Versione di esempio | Quando si applica |
|---|---|---|
| MAJOR | `2.0.0` | Cambiamenti incompatibili e migrazioni |
| MINOR | `1.14.0` (pubblicata) | Funzionalità retrocompatibili significative |
| PATCH | `1.14.1` (pubblicata) | Correzioni ordinarie, manutenzione e stabilità |
| HOTFIX | `1.14.0.1` (esempio futuro) | Correzione urgente di una release già pubblicata |
| BUILD | `1.14.0+ci.<run>.<sha>` (formato) | Compilazione senza incremento di versione funzionale |

Un HOTFIX incrementa il quarto componente della release di riferimento. La successiva PATCH o MINOR incorpora la correzione e azzera il quarto componente. Non utilizzare un HOTFIX per distinguere semplici ricompilazioni. Non attribuire numeri di esempio a release non ancora pubblicate.

## Controllo versioning obbligatorio prima di ogni merge

ChatGPT, unico responsabile dei merge, deve verificare il versioning di **ogni** PR, anche quando non modifica la versione: confronta `version.py`, `version_info.txt`, l'ultima Release/tag pubblicata, `CHANGELOG.md`, `RELEASE_NOTES.it.md` e le altre PR pendenti. Registra per ciascuna richiesta la categoria MAJOR/MINOR/PATCH/HOTFIX oppure **BUILD-only, senza incremento della versione funzionale**, con motivazione.

Se più PR vengono integrate insieme, la categoria/versione finale è stabilita **una sola volta sul risultato congiunto**, risolvendo prima numeri duplicati, conflitti di changelog, dipendenze e compatibilità dell'updater. La sequenza di merge segue [AGENTS.md](AGENTS.md): priorità alle modifiche ChatGPT, poi Claude; dentro ciascun gruppo, importanza decrescente e cronologia originale crescente. Tale sequenza non autorizza merge tecnicamente incoerenti né pubblicazioni automatiche.

Un merge ordinario non rappresenta di per sé una nuova release. Rimangono obbligatori i test e i controlli di compilazione e, per le pubblicazioni MAJOR/MINOR, il gate manuale esistente.

## Procedura di rilascio

1. Aggiornare insieme `version.py` e `version_info.txt`.
2. Inserire la sezione corrispondente nel `CHANGELOG.md`. MAJOR e MINOR richiedono le sezioni **Sintesi**, **Funzionalità** e **Correzioni**, con evidenze verificabili.
3. Aggiornare `RELEASE_NOTES.it.md` e, quando serve, i README e la documentazione correlata.
4. Eseguire test automatici, build Windows, verifica della versione nell'EXE, scansione Defender e controllo degli SHA-256.
5. Per MAJOR e MINOR, richiedere l'approvazione esplicita tramite il workflow manuale GitHub Actions; la semplice compilazione non pubblica un nuovo numero di release. È ammessa soltanto l'eccezione tracciata e vincolata a v1.15.0 descritta sopra, su richiesta esplicita del proprietario.
6. Pubblicare solo pacchetti verificati, con tag e versione interna coincidenti, senza riscrivere le release già pubblicate.
7. Validare l'updater su Windows reale prima di considerare completamente collaudato il percorso di aggiornamento.

## Integrità e documentazione

Ogni ZIP ufficiale deve avere un digest SHA-256 verificabile. `BUILD_INFO.txt` identifica la compilazione e il commit; la scansione Microsoft Defender **non** sostituisce una firma digitale Authenticode. Indicare sempre lo stato effettivo della firma e le limitazioni.

- [Download e Release ufficiali](https://github.com/matiz311/WinNAT-UI/releases)
- [Changelog tecnico](CHANGELOG.md)
- [Note di rilascio per gli utenti](RELEASE_NOTES.it.md)
- [Issue aperte](https://github.com/matiz311/WinNAT-UI/issues?q=is%3Aissue+is%3Aopen)
