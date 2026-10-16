# Migrazione storica SemVer (proposta, non ancora applicata)

Obiettivo: sostituire la numerazione storica incoerente con una sequenza **univoca e monotona**. La colonna «nuova» è il numero dell'eseguibile che dovrà essere **ricompilato dal commit originale**. Non è consentito rinominare il tag mantenendo un EXE con versione diversa.

| Vecchia | Nuova | Classe |
|---|---|---|
| `v1.2.0` | `v1.2.0` | MINOR |
| `v1.3.0` | `v1.3.0` | MINOR |
| `v1.4.0` | `v1.4.0` | MINOR |
| `v1.6.0` | `v1.5.0` | MINOR |
| `v1.6.1` | `v1.5.1` | PATCH |
| `v1.7.0` | `v1.5.2` | PATCH |
| `v1.7.1` | `v1.6.0` | MINOR |
| `v1.7.2` | `v1.6.1` | PATCH |
| `v1.7.3` | `v1.6.2` | PATCH |
| `v1.7.4` | `v1.6.3` | PATCH |
| `v1.7.5` | `v1.6.4` | PATCH |
| `v1.8.0` | `v1.7.0` | MINOR |
| `v1.9.0` | `v1.8.0` | MINOR |
| `v1.9.1` | `v1.9.0` | MINOR |
| `v1.9.2` | `v1.9.1` | PATCH |
| `v1.9.3` | `v1.10.0` | MINOR |
| `v1.9.4` | `v1.10.1` | PATCH |
| `v1.9.5` | `v1.10.2` | PATCH |
| `v1.9.6` | `v1.11.0` | MINOR |
| `v1.9.7` | `v1.11.1` | PATCH |
| `v1.9.8` | `v1.11.2` | PATCH |
| `v1.9.9` | `v1.12.0` | MINOR |
| `v1.9.10` | `v1.12.1` | PATCH |
| `v1.9.11` | `v1.12.2` | PATCH |
| `v1.9.12` | `v1.12.3` | PATCH |
| `v1.9.13` | `v1.12.4` | PATCH |
| `v1.9.14` | `v1.12.5` | PATCH |
| `v1.9.15` | `v1.13.0` | MINOR |
| `v1.9.15.1` | `v1.13.0.1` | HOTFIX |
| `v1.10.0` | `v1.14.0` | MINOR |

## Controlli di preflight obbligatori

1. Inventario autenticato, completo e salvato di tutte le GitHub Releases, tag (inclusi quelli privi di release), asset con digest, commit SHA e artefatti ancora disponibili; verificare eventuali tag creati dopo questa proposta.
2. Verificare per ogni versione la disponibilità del sorgente originale e la riproducibilità del build su runner Windows. Non sostituire la logica di una vecchia release con quella corrente.
3. Fare backup esterno dei contenuti dei rilasci e dell'integrità SHA256 degli asset; la ricompilazione non mantiene necessariamente lo stesso digest.
4. Validare uno per uno i mapping, inclusa la release errata `v1.10.1` del 14 ottobre (se ritirata non trattarla come un rilascio reale).
5. Preparare tutti i pacchetti rinumerati in area **non pubblica**, con versione Python, risorsa VERSIONINFO, SHA256 e release notes coincidenti.
6. Verificare la compatibilità dell'updater con un utente che ancora esegue un vecchio EXE; implementare eventuale tabella `old→new` prima del cambio di release/latest.
7. Solo dopo un esito completamente positivo pubblicare la sequenza nuova con tag nuovi e asset verificati. Gestire i tag storici conflittuali tramite una fase di transizione atomica quanto consentito dalle API, con piano di recupero.
8. Verificare la pagina Releases, il tag latest, download, checksum, note, link issue e aggiornamento da una versione storica.

## Vincoli

- La sola riclassificazione documentale non è una rinumerazione.
- Non usare `--force` o sovrascrivere SHA e asset storici senza backup.
- Non creare release vuote o tag alias che puntino a eseguibili con numerazione differente.
- Non inserire in `main` script di migrazione una tantum dopo il completamento: lavorare su branch dedicato, riportando in `main` solo codice, policy e documentazione definitiva.
- Il progetto mantiene l'estensione a quattro componenti `MAJOR.MINOR.PATCH.HOTFIX` per le sole correzioni urgenti a una release già pubblicata. È una convenzione del progetto (non SemVer 2.0.0 puro). `1.9.15.1` diventa quindi `1.13.0.1`. Le normali correzioni successive usano PATCH (`1.13.1`), dopo aver integrato gli eventuali HOTFIX; la componente HOTFIX torna a zero a ogni incremento PATCH, MINOR o MAJOR.
- Sequenza consentita: `1.13.0` → `1.13.0.1` → `1.13.0.2` → `1.13.1` → `1.14.0`. Non creare `1.13.0.1` prima di `1.13.0`, né cambiare un HOTFIX già pubblicato.
- Questa tabella deriva dal changelog, **non** costituisce ancora un inventario verificato dei tag e degli asset realmente presenti.
