# Phase 2B engineering lessons

1. Legacy Yahoo/FRED caches lose synthetic-fallback provenance and the original volume loader fills failures with 1,000,000. The original indicator pack also invents high/low from close. Consequence: plausible but unverifiable research scores. Prevention: new snapshot namespace, hashed original provider payload, explicit field quality and no synthetic fallback or ffill. Regression tests cover missing volume, corrupt hashes and synthetic rejection.
2. Legacy `test_data_quality_report_builds` assumes `bdate_range(end=Saturday, periods=30)` always contains 30 rows. On this pandas/runtime it returns 29. Prevention: derive fixture values from the returned index length. No financial model changes.
3. The execution sandbox forbids binding a localhost TCP server (`PermissionError: Operation not permitted`). Never describe an HTTP preview as running without observed success. Use Streamlit AppTest for runtime and interactions, and report the remaining browser/HTTP verification gap explicitly.

4. Un controllo limitato a gap superiori a sette giorni accetta sedute interne saltate. Usare il calendario del venue per ETF/equity; fuori dagli anni supportati degradare. Per macro controllare freschezza, finitezza e continuità mensile. Test coprono entrambe le regressioni.
5. Il cutoff as-of deve valere anche per storico run e delta, con timestamp UTC canonico. Il Core corrente va separato dalle viste storiche. Le letture SQLite non devono inizializzare lo schema o scrivere.

6. Phase 2B.1: i test UI devono coprire anche l'assenza totale di metriche e la migrazione dal payload precedente. Campi del radar non presenti ricevono uno stato assente/False descrittivo, mai metriche numeriche inventate; il fallback della vista usa la registry e blocca ogni opportunità priva di input.
7. Pubblicazione: la shortlist di un host pubblico non può condividere una preferenza SQLite fra visitatori. La versione pubblica usa session state e disabilita le letture Core. Le fonti vengono acquisite dal server; non si pubblica il database del Mac.

8. Il test di orchestrazione legacy non deve dipendere da richieste Yahoo non limitate: due suite sono state interrotte in yfinance.multi.download. La regressione del workflow usa adapter offline esplicitamente nel solo test. Acquisizione reale e controlli finanziari restano separati.

9. Lo screenshot mobile mostra un falso avviso di outage insieme a dati parziali e nessun run completato. Un lock occupato è RUNNING, non un fallimento delle fonti. Non promuovere i frammenti del primo caricamento; usare avanzamento asincrono e un evento di completamento distinto. Le metriche desktop impilate sul telefono spostavano la Top10 troppo in basso: il contesto deve essere compatto e le opportunità devono avere una vista a schede.
