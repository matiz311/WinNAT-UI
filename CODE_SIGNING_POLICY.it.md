# Politica di firma del codice

**Italiano** | [English](CODE_SIGNING_POLICY.md)

## Stato
La firma digitale tramite SignPath Foundation **non è stata ancora approvata né abilitata**. L'eseguibile attuale non è firmato. Questo documento descrive la procedura prevista, non un certificato già disponibile.

## Progetto
- Repository: https://github.com/matiz311/WinNAT-UI
- Licenza: MIT
- Autore dei commit / manutentore: [matiz311](https://github.com/matiz311)
- Revisore (attuale manutentore): [matiz311](https://github.com/matiz311)
- Responsabile dell'approvazione delle release: [matiz311](https://github.com/matiz311)

## Controlli sulle release
- In caso di approvazione, le release firmate devono derivare dal repository pubblico ufficiale e da un workflow GitHub Actions verificato.
- L'approvazione delle release firmate deve essere esplicita e utilizzare il workflow protetto del servizio di firma.
- La riuscita della compilazione e la scansione Defender sono prerequisiti, ma non garantiscono che il programma sia privo di malware.
- Nessuna credenziale, chiave privata o token di firma viene inserito nel sorgente o nell'output.
- I collaboratori devono utilizzare l'autenticazione multifattore per gli accessi a GitHub e al servizio di firma.

## Privacy
Il programma non trasferisce informazioni a sistemi remoti, salvo le operazioni di networking richieste dall'utente o dall'amministratore che lo utilizza. Consulta lo stato della rete Windows e salva snapshot JSON locali. Una volta configurato, Windows inoltra il traffico verso le destinazioni richieste dai dispositivi collegati. L'applicazione non implementa telemetria.

Consulta anche l'[informativa privacy](PRIVACY.it.md).

## Attribuzione futura a SignPath
Solo **dopo l'eventuale approvazione** del progetto, la pagina della release riporterà la dicitura richiesta:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation

Riferimenti: https://signpath.org/terms.html e https://signpath.org/apply.html.
