# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/); versioni secondo [Semantic Versioning](https://semver.org/lang/it/).

Regole del progetto:
- **MAJOR**: cambi incompatibili (es. formato dello stato salvato, requisiti di sistema).
- **MINOR**: nuove funzioni o cambi visibili dell'interfaccia.
- **PATCH**: sole correzioni, nessuna funzione nuova.
- La versione si cambia solo in `version.py`; ogni release ha qui una sezione `## [x.y.z]`, da cui la CI prende le note.
- I tag già pubblicati non vengono mai spostati o rinominati (gli ZIP e gli SHA256 distribuiti resterebbero orfani): eventuali errori si correggono qui e nelle note della release.

## [1.9.1] - 2026-10-14
### Cambiato
- **WAN dinamiche**: la configurazione parte con una sola WAN (la WAN secondaria non è più richiesta). Con «+ Aggiungi WAN» se ne possono aggiungere fino a quante interfacce ha il PC, riordinarle per priorità e rimuoverle; le metriche devono crescere secondo la priorità e viene proposta automaticamente la successiva (+40).
- **Subnet LAN automatica**: scegliendo l'interfaccia LAN viene rilevato l'IPv4 già presente (preferiti gli indirizzi manuali, ignorati APIPA 169.254.x.x): diventa statico, senza gateway, e il NAT usa quella subnet. Se la scheda non ha un IPv4 utilizzabile si usa 10.10.10.0/24 con IP 10.10.10.1. Un'etichetta indica se i valori sono rilevati, predefiniti o modificati a mano.
- Se si sceglie come LAN una scheda già usata come WAN, viene tolta dalle WAN; cambiando la subnet a mano l'IP del PC passa al primo indirizzo valido.
### Aggiunto
- Blocco se la subnet LAN si sovrappone alla rete di una WAN.
- Schema topologico con N WAN (primaria piena, riserve tratteggiate).
### Compatibilità
- I profili con `wan1`/`wan2`/`metric1`/`metric2` restano accettati; il rollback introdotto nella 1.9.0 copre tutte le WAN configurate.

## [1.9.0] - 2026-10-14
### Aggiunto
- Rollback compensativo automatico su commit non riusciti: ripristina esclusivamente le risorse di rete coinvolte (IPv4, DHCP, route esplicite, forwarding, metriche, WinNAT, IPEnableRouter) secondo lo snapshot iniziale.
- Verifica finale delle modifiche monitorate e report Debug con comandi eseguiti, errori e differenze residue. Se lo stato non è verificabile, segnala rollback incompleto.
### Limitazioni
- Non è una transazione di Windows: APIPA, sessioni NAT, mapping statici preesistenti, stato di rete esterno e modifiche contemporanee potrebbero non essere ripristinabili. Prima di ogni commit viene comunque salvato uno snapshot JSON.

## [1.8.0] - 2026-10-14
### Aggiunto
- `tools/WinNAT-Diagnostica.ps1`: diagnostica di compatibilità in sola lettura (sistema, schede, IPv4, route, WinNAT, ICS, Hyper-V) con verdetto e indicazione delle schede utilizzabili come LAN/WAN; produce un report `.txt` e `.json` da allegare alle segnalazioni. Eseguito in CI come smoke test.

## [1.7.5] - 2026-10-14
### Corretto
- Finestra d'errore: il riepilogo mostra il primo messaggio utile dello stderr invece delle intestazioni ("ESECUZIONE POWERSHELL NON RIUSCITA", exit code); finestra centrata, coerente con il tema chiaro/scuro, dettagli tecnici a scomparsa, Esc per chiudere. Anche il messaggio di stato nella barra laterale mostra una sola riga leggibile.
- Output PowerShell letto in UTF-8: nomi di schede e messaggi con lettere accentate non risultano più corrotti (code page OEM 850 su Windows in italiano).
- Note delle release già pubblicate riallineate al CHANGELOG tramite il workflow manuale "Sync release notes" (tag e file scaricabili invariati).
- Versioning: unica fonte in `version.py`; versione file Windows, tag e note di release derivati automaticamente e verificati dai test. Le note di release non sono più scritte a mano nel workflow (in passato v1.3.0 e v1.6.1 avevano note copiate da altre versioni).

## [1.7.4] - 2026-10-14
### Cambiato
- Errori PowerShell più completi: exit code, interprete, timeout, stderr e stdout integrali e script eseguito con righe numerate (per confrontare «In riga:X»).

## [1.7.3] - 2026-10-14
### Corretto
- IP statico LAN: `netsh` poteva segnalare un falso errore "oggetto già esistente"; ora lo stato reale della LAN viene verificato e i conflitti di indirizzo diagnosticati prima di considerare l'operazione fallita.

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
- IP statico LAN su schede con DHCP in PersistentStore (`netsh ... store=persistent`) e recupero dopo un Commit fallito.
### Nota
- Contiene ancora l'**interfaccia precedente** (1.6.x): la nuova grafica arriva con la 1.7.1.

## [1.6.1] - 2026-10-14
### Corretto
- Prima correzione del conflitto PersistentStore/DHCP sull'IP statico LAN, con test di regressione.

## [1.6.0] - 2026-10-14
### Aggiunto
- Configurazione completa da PC vergine secondo la guida «NAT e Routing IPv4 su Windows 11»: LAN, WAN primaria e secondaria con metriche, IPEnableRouter, forwarding, NAT; Disabilita e Ripristina espliciti.

## [1.5.0] - non pubblicata
- Numero saltato: nessuna release 1.5.0 è stata distribuita.

## [1.4.0] - 2026-10-14
### Aggiunto
- Rimozione di configurazioni NAT preesistenti create fuori dall'app; raccolta dell'inventario in parallelo.

## [1.3.0] - 2026-10-14
### Aggiunto
- Dashboard di configurazione, modifiche candidate con Commit, sessioni NAT separate, barra di avanzamento.

## [1.2.0] - 2026-10-14
### Aggiunto
- Prima release binaria pubblica: modifiche pendenti e Commit una alla volta.
### Nota
- Incoerenza nota: il titolo della finestra mostra "1.1.0", la scheda Informazioni e le proprietà del file "1.2.0". La versione corretta è 1.2.0.

