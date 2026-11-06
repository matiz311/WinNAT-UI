# Piano di pubblicazione — PATCH v1.17.1

Stato: preparazione; nessuna GitHub Release ancora pubblicata.

Sorgente di integrazione: [PR #92](https://github.com/matiz311/WinNAT-UI/pull/92), merge commit `d8b8f69d2525a6398cac18008ea6282046fd990a`. Include anche la correzione della finestra diagnostica [PR #88](https://github.com/matiz311/WinNAT-UI/pull/88).

Correzioni candidate:
- #82: impedisce di usare adattatori Bluetooth PAN come interfacce del gateway.
- #83: non blocca il commit per la sola scomparsa di ICS inattivo di adattatore VPN non selezionato, mantenendo le protezioni sulle interfacce e condivisioni rilevanti.
- #87: rende visibili i pulsanti di invio OpenIssue nella diagnostica.

Esclusioni:
- #76: incompatibilità Malwarebytes VPN non diagnosticata e non risolta.
- #91: monitoraggio continuo delle WAN degradate, ancora da sviluppare.
- #81 e #84: PR non incluse, riconciliazione separata.

Gate: preregistrare manutenzione secondo AGENTS.md; aggiornare insieme versione Python, metadata Windows, changelog e note; compilare il tree finale su CI Windows; verificare i test, scansione Defender, checksum e aggiornamento GitHub. Non chiudere #82/#83/#87 per il solo merge o per una build CI: attendere test operativo Windows reale. Il rilascio può modificare i download e l'indice releases/latest; conservare la release precedente e non riscrivere i tag pubblicati.
