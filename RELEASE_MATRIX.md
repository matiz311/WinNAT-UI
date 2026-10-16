# Registro dei rilasci e classificazione SemVer

Questo registro distingue **tag storico** (identificativo realmente distribuito) e **classe funzionale** (MINOR, PATCH, HOTFIX, ritirata). La classificazione non autorizza a cambiare il tag sullo stesso binario: `version.py`, VERSIONINFO Windows, SHA-256, tag, Release e aggiornamento automatico devono rimanere coerenti.

| Tag/versione storica | Classe | Stato e ambito |
| --- | --- | --- |
| 1.2.0 | MINOR | Prima build pubblica e Commit |
| 1.3.0 | MINOR | Dashboard, configurazione candidata |
| 1.4.0 | MINOR | Rimozione NAT esterni |
| 1.5.0 | NON PUBBLICATA | Numero saltato |
| 1.6.0 | MINOR | Setup gateway completo |
| 1.6.1 | PATCH | PersistentStore/DHCP |
| 1.7.0 | PATCH (numerazione storica MINOR) | Ripristino indirizzi LAN |
| 1.7.1 | MINOR funzionale (tag PATCH storico) | Riprogettazione UI |
| 1.7.2 | PATCH | Finestra diagnostica |
| 1.7.3 | PATCH | Verifica IP statico |
| 1.7.4 | PATCH | Diagnostica PowerShell |
| 1.7.5 | PATCH | Errori e UTF-8 |
| 1.8.0 | MINOR | Script di diagnostica |
| 1.9.0 | MINOR | Rollback compensativo |
| 1.9.1 | MINOR funzionale (tag PATCH storico) | WAN multiple e LAN automatica |
| 1.9.2 | PATCH | Normalizzazione WAN dinamiche |
| 1.9.3 | MINOR funzionale (tag PATCH storico) | Aggiornamento automatico |
| 1.9.4 | PATCH | Console Commit |
| 1.9.5 | PATCH | Segnalazione guidata |
| 1.9.6 | MINOR funzionale (tag PATCH storico) | Tracking e segnalazione anonima in attesa di backend |
| 1.9.7 | PATCH | Errori reporting |
| 1.9.8 | PATCH | Disaccoppiamento API Issue |
| 1.9.9 | MINOR funzionale (tag PATCH storico) | Commit idempotente a differenze |
| 1.9.10 | PATCH | Preflight NAT |
| 1.9.11 | PATCH (backend) | Port mapping e IP secondari |
| 1.9.12 | PATCH | Packaging |
| 1.9.13 | PATCH | Preflight creazione NAT |
| 1.9.14 | PATCH | Coesistenza LAN |
| 1.9.15 | MINOR funzionale (tag PATCH storico) | Aggregazione reti WinNAT |
| 1.9.15.1 | HOTFIX | Add NAT diretto, nessuna ricostruzione |
| 1.10.0 | MINOR | Gateway segnalazioni live e updater |
| 1.10.1 del 14 ottobre | RITIRATA | Pubblicazione errata, non coincide con eventuale 1.10.1 futura |

## Criterio di riallineamento

**Non sovrascrivere né spostare i tag pubblicati**: spostare `v1.7.1` o riutilizzare `v1.8.0` produrrebbe riferimenti sbagliati a codice ed eseguibili. Anche alias di tag con numerazione diversa dall'eseguibile sarebbero fuorvianti. Le classi funzionali sopra sono una riclassificazione documentale retroattiva, non una falsa dichiarazione che la versione Windows sia differente.

Una vera rinumerazione completa richiede ricompilazione di ogni versione, verifica dell'updater, nuovo SHA-256, nuovi asset firmati/verificati e compatibilità con le installazioni già distribuite; non è possibile correggere in modo sicuro soltanto un tag Git.

## Note obbligatorie per ogni release futura

- **Tipo:** MAJOR / MINOR / PATCH / HOTFIX; le BUILD non diventano release.
- **Sintesi e novità:** distinguere funzioni effettivamente disponibili da backend non ancora attivati.
- **Bugfix e sicurezza:** comportamento precedente e corretto.
- **Compatibilità e migrazioni:** nuovi requisiti e modifiche distruttive o interruzioni previste.
- **Test e limitazioni:** distinguere CI e test reali Windows.
- **Open Issues:** link dinamico alle Issue aperte del repository, senza ascrivere arbitrariamente una Issue a una versione.
- **Integrità:** tag, commit, SHA256 e avviso sulla firma effettiva.

Open issues correnti: https://github.com/matiz311/WinNAT-UI/issues?q=is%3Aissue+is%3Aopen

Note in italiano per ogni versione storica: [RELEASE_NOTES.it.md](RELEASE_NOTES.it.md). Dettaglio tecnico originale: [CHANGELOG.md](CHANGELOG.md).
