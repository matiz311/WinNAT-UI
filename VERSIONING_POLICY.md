# Politica di versioning e build

## Identificatori distinti
- **Versione funzionale**: `MAJOR.MINOR.PATCH` in `version.py`, riportata nelle proprietà Windows dell'EXE, nelle release ufficiali e nel changelog.
- **Identificativo build**: `MAJOR.MINOR.PATCH+ci.<run_number>.<short_sha>`, registrato nel file `BUILD_INFO.txt` all'interno dell'artifact. Ogni esecuzione CI ha un artifact univoco anche se la versione funzionale rimane invariata.
- Un test di compilazione, refactoring, revisione documentale o ripetizione della pipeline **non incrementa automaticamente** la versione funzionale.

## Quando aggiornare la versione
| Tipo | Esempio | Criterio |
| --- | --- | --- |
| PATCH | 1.9.2 → 1.9.3 | Bugfix, sicurezza, stabilità, diagnostica o miglioramenti senza nuove funzionalità rilevanti. |
| MINOR | 1.9.x → 1.10.0 | Pacchetto significativo di nuove funzionalità, miglioramenti operativi e correzioni, consolidato e verificato. |
| MAJOR | 1.x.y → 2.0.0 | Cambi incompatibili, revisione sostanziale dei requisiti o del modello applicativo. |

Il passaggio MINOR **non deriva dal numero di build** e non avviene automaticamente quando si aggiunge una singola correzione o una funzione isolata. Le correzioni successive restano nella stessa serie PATCH finché non viene pianificato un rilascio funzionale significativo.

## Procedura obbligatoria per MINOR/MAJOR
1. Preparare la proposta con il changelog dettagliato, raggruppando tutte le feature e le correzioni dall'ultima versione MINOR.
2. Inserire nella nuova sezione `## [X.Y.0]` del `CHANGELOG.md` **tutte** le intestazioni `### Sintesi`, `### Funzionalità`, `### Correzioni`; descrivere valore operativo, compatibilità, limiti, test eseguiti e problemi noti. Almeno una voce concreta sia per funzionalità sia per correzioni.
3. Esaminare e approvare esplicitamente il riepilogo **prima** della pubblicazione. L'approvazione viene espressa da chi avvia manualmente la workflow `Build Windows executable` dal branch `main`, selezionando `approve_feature_release`. Questo selettore è una conferma operativa, non un sistema di approvazione a più persone.
4. La CI esegue comunque build e test a ogni push/PR, ma **non pubblica automaticamente** un cambio MINOR/MAJOR. Il controllo blocca salti numerici e pubblicazioni prive di note strutturate.
5. Conservare immutabili i tag già pubblicati; non sovrascrivere pacchetti o SHA256 esistenti.

Per la versione PATCH la pipeline può pubblicare automaticamente una release quando `version.py` aumenta di un solo PATCH e il changelog corrispondente è presente. A versione invariata produce esclusivamente artifact numerati.

## Eccezioni storiche
Le release `v1.10.1` e altre versioni già distribuite non vanno rinominate né cancellate retroattivamente. La cronologia contiene un precedente salto improprio: il ramo funzionale corrente rimane nella serie 1.9.x secondo `CHANGELOG.md`. Nei prossimi rilasci non introdurre altri salti o numeri fittizi per compensarlo.

## Consultare la build
Aprire `BUILD_INFO.txt` nell'artifact per identificare versione, numero run, commit e workflow. Per le release pubbliche il riferimento permanente è il tag Git associato e il relativo hash SHA256.
