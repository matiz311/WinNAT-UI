# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/); versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

Regole del progetto:
- **MAJOR**: cambi incompatibili (es. formato dello stato salvato, requisiti di sistema).
- **MINOR**: nuove funzioni o cambi visibili dell'interfaccia.
- **PATCH**: sole correzioni, nessuna funzione nuova.
- La versione si cambia solo in `version.py`; ogni release ha qui una sezione `## [x.y.z]`, da cui la CI prende le note.

## [1.8.0] - 2026-10-14
### Aggiunto
- `tools/WinNAT-Diagnostica.ps1`: diagnostica di compatibilità in sola lettura (sistema, schede, IPv4, route, WinNAT, ICS, Hyper-V) con verdetto e indicazione delle schede utilizzabili come LAN/WAN; produce un report `.txt` e `.json` da allegare alle segnalazioni. Eseguito in CI come smoke test.

## [1.7.3] - 2026-10-14
### Corretto
- Finestra d'errore: il riepilogo mostra il primo messaggio utile invece di "PowerShell exit code: 1"; finestra centrata, coerente con il tema chiaro/scuro, dettagli tecnici a scomparsa, Esc per chiudere. Anche il messaggio di stato nella barra laterale mostra una sola riga leggibile.
- Output PowerShell letto in UTF-8: nomi di schede e messaggi con lettere accentate non risultano più corrotti (code page OEM 850 su Windows in italiano).
- Versioning: unica fonte in `version.py`; versione file Windows, tag e note di release derivati automaticamente e verificati dai test. Le note di release non sono più scritte a mano nel workflow (in passato v1.3.0 e v1.6.1 avevano note copiate da altre versioni).

## [1.7.2] - 2026-10-14
### Aggiunto
- Finestra d'errore con dettagli di debug copiabili: output PowerShell completo (stdout/stderr, exit code) e traceback Python.

## [1.7.1] - 2026-10-14
### Cambiato
- Nuova interfaccia: navigazione laterale, Panoramica con verdetto sullo stato del gateway, schema topologico LAN → PC → WAN, validazione dei campi in tempo reale, barra delle modifiche persistente, tema chiaro/scuro. *Per le regole sopra sarebbe stata una MINOR (1.8.0).*
### Corretto
- Ripristino del DHCP LAN idempotente quando il DHCP è già attivo.

## [1.7.0] - 2026-10-14
### Corretto
- IP statico LAN su schede con DHCP in PersistentStore (`netsh ... store=persistent`) e recupero dopo un Commit fallito. Interfaccia invariata rispetto alla 1.6.x.

## [1.6.1] - 2026-10-14
### Corretto
- Prima correzione del conflitto PersistentStore/DHCP sull'IP statico LAN, con test di regressione.

## [1.6.0] - 2026-10-14
### Aggiunto
- Configurazione completa da PC vergine secondo la guida «NAT e Routing IPv4 su Windows 11»: LAN, WAN primaria e secondaria con metriche, IPEnableRouter, forwarding, NAT; Disabilita e Ripristina espliciti.

## [1.4.0] - 2026-10-14
### Aggiunto
- Rimozione di configurazioni NAT preesistenti create fuori dall'app; raccolta dell'inventario in parallelo.

## [1.3.0] - 2026-10-14
### Aggiunto
- Dashboard di configurazione, modifiche candidate con Commit, sessioni NAT separate, barra di avanzamento.

## [1.2.0] - 2026-10-14
### Aggiunto
- Prima release binaria pubblica: modifiche pendenti e Commit una alla volta.
