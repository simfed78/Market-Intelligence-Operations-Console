# Phase 2B — Changelog Top Opportunities

7 novembre 2026.

- La home `Overview` ora apre con **Top Opportunities**, una tabella con massimo dieci priorità per approfondimento e drill-down esplicabile.
- L’ordinamento è deterministico: prontezza di ricerca (`research candidate`, `watch`, `blocked`), score tecnico dell’orizzonte selezionato, ticker.
- La tabella dichiara separatamente score/momentum, conferma tecnica, rischio di volatilità, qualità del volume, qualità dei flow, fonte e timestamp; non combina dati flow, fondamentali o macro assenti con il punteggio tecnico.
- Gli strumenti degradati, mancanti e sintetici sono esclusi dalla Top 10, anche se un payload errato li marca come idonei.
- Un possibile candidato d’ingresso resta fail-closed: richiede flow `VALID`, conferma tecnica e volume completi, più `RESEARCH_ONLY`, gate Phase 1/2 `OPEN` e `DEMO_READ_ONLY`. Con i gate e i dati correnti, la dashboard mostra soltanto priorità di ricerca.
- Nessuna modifica al Trading Desk Core, nessuna chiamata broker, nessun ordine e nessuna scrittura oltre alla shortlist già esistente.
