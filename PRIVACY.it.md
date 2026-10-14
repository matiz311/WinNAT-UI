# Informativa sulla privacy — WinNAT UI

**Italiano** | [English](PRIVACY.md)

Ultimo aggiornamento: 14 ottobre 2026.

WinNAT UI è un'utilità open source per Windows che opera localmente, mantenuta da Matteo Cannizzo. Questa informativa descrive il comportamento attuale del codice sorgente.

## Dati elaborati localmente
Per mostrare la configurazione di rete ed eseguire diagnosi di WinNAT, l'applicazione consulta nomi e descrizioni delle schede di rete, indirizzi IPv4, route, gateway, regole e sessioni NAT, stato dell'inoltro IPv4 e impostazioni di Internet Connection Sharing (ICS). Questi dati possono comprendere indirizzi IP pubblici e privati e informazioni sulla topologia di rete.

Prima di modificare la configurazione, l'applicazione salva uno snapshot diagnostico JSON in `%LOCALAPPDATA%\WinNAT-UI\backups\`. Quando si utilizza la procedura guidata, viene salvato il file di stato `%LOCALAPPDATA%\WinNAT-UI\managed-setup.json`. L'utente può inoltre esportare manualmente i dati diagnostici in un file JSON a sua scelta.

## Trasmissioni e servizi terzi
L'applicazione non implementa telemetria, analisi statistiche, tracciamento, account remoti, aggiornamenti automatici o invio di dati diagnostici al manutentore. La sua funzione è configurare il networking Windows e il NAT, tramite cui i dispositivi collegati possono poi comunicare con servizi Internet scelti dagli stessi dispositivi. Windows, gli strumenti di sicurezza endpoint e i servizi terzi possono operare secondo proprie informative sulla privacy.

GitHub tratta dati quando visiti il repository o scarichi una release: consulta l'[informativa privacy di GitHub](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Conservazione ed eliminazione
I file diagnostici locali rimangono sul dispositivo fino alla loro eliminazione da parte dell'utente. Attualmente l'applicazione non elimina né ruota automaticamente i vecchi backup e non possiede un database centrale degli utenti.

Per eliminare i dati locali, chiudi WinNAT UI e rimuovi `%LOCALAPPDATA%\WinNAT-UI\`, dopo aver conservato gli eventuali backup necessari. Questa operazione **non annulla** le modifiche di rete apportate a Windows: utilizza prima, se applicabile, la rimozione guidata della configurazione.

## Sicurezza
Per cambiare le impostazioni di rete possono essere richiesti privilegi amministrativi. I dati diagnostici esportati possono essere sensibili, soprattutto se mostrano topologia e sessioni NAT attive. L'eseguibile rimane non firmato fino all'attivazione di una procedura di firma approvata; la scansione antivirus in CI non garantisce l'assenza di codice dannoso.

## Contatti
Per domande sulla privacy, apri una segnalazione su [GitHub Issues](https://github.com/matiz311/WinNAT-UI/issues), senza includere indirizzi privati, credenziali o file diagnostici con informazioni riservate.
