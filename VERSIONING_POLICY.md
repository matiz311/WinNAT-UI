# Versioning e pubblicazione — WinNAT-UI

## Stato attuale — 17 ottobre 2026

La **release stabile pubblicata è v1.16.0**: [GitHub Releases](https://github.com/matiz311/WinNAT-UI/releases/latest). La patch ha corretto il fallback del logo Windows. Il catalogo comprende 33 release pubbliche fino alla v1.16.0. Le ultime versioni sono `v1.13.0` → `v1.13.0.1` → `v1.14.0` → `v1.14.1` → `v1.15.0` → `v1.15.1` → `v1.16.0`.

**v1.16.0 è una release MINOR pubblicata il 17 ottobre 2026.** Comprende gestione avanzata delle segnalazioni bug, diagnosi dell'updater, notifiche di errori d'installazione e registro manutenzioni. Si applicano la convalida combinata del ramo di integrazione, l'esame della sicurezza e il gate di approvazione della release. Per v1.15.0 esisteva un'autorizzazione eccezionale, limitata a quel rilascio. Il 17 ottobre 2026 il proprietario ha autorizzato espressamente ChatGPT a integrare, verificare e pubblicare la v1.16.0 in autonomia: per questa sola release il workflow riconosce la registrazione `release-approvals/v1.16.0.md` se il commit precedente su `main` e l'elenco completo dei file modificati coincidono con i valori prestabiliti. L'autorizzazione non disabilita build, test, Defender, gate versione, verifica della release esistente o controllo dell'HEAD e non vale per versioni successive.

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
5. Per MAJOR e MINOR, richiedere l'approvazione esplicita tramite il workflow manuale GitHub Actions; la semplice compilazione non pubblica un nuovo numero di release. Sono ammesse soltanto le eccezioni strettamente delimitate e tracciate per v1.15.0 e v1.16.0 sopra descritte, entrambe su richiesta esplicita del proprietario.
6. Pubblicare solo pacchetti verificati, con tag e versione interna coincidenti, senza riscrivere le release già pubblicate.
7. Validare l'updater su Windows reale prima di considerare completamente collaudato il percorso di aggiornamento.

## Integrità e documentazione

Ogni ZIP ufficiale deve avere un digest SHA-256 verificabile. `BUILD_INFO.txt` identifica la compilazione e il commit; la scansione Microsoft Defender **non** sostituisce una firma digitale Authenticode. Indicare sempre lo stato effettivo della firma e le limitazioni.

- [Download e Release ufficiali](https://github.com/matiz311/WinNAT-UI/releases)
- [Changelog tecnico](CHANGELOG.md)
- [Note di rilascio per gli utenti](RELEASE_NOTES.it.md)
- [Issue aperte](https://github.com/matiz311/WinNAT-UI/issues?q=is%3Aissue+is%3Aopen)
