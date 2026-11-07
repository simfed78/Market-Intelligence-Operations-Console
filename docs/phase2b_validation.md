# Phase 2B — registro di verifica

7 novembre 2026. **IMPLEMENTED / TESTED**. Nessuna dichiarazione di production readiness.

## Preservazione e audit

GitHub HEAD `5928d3404503a0b6ab797a62c598098e50c0d5cd` verificato via connector e coincidente con il checkout locale. Sviluppo sul branch isolato `phase2b/dashboard-mvp`; nessuna fusione dei repository. Helper locale preesistente di sei righe in `app/dashboard.py` conservato; altri file duplicati non tracciati nell'originale lasciati intatti. Stato Git originale ricontrollato e invariato.

Il Core originale non è un checkout Git; nessun file Core modificato. Nessuna chiamata eToro, lettura credenziali o copia di chiavi. Dati e riferimento locale al runtime sono ignorati da Git.

## Acquisizione reale

145 strumenti e otto serie FRED: 153 sorgenti importate, zero errori. Ultimo import `2026-11-07T09:02:22.804012+00:00`; ogni payload conserva il proprio timestamp di acquisizione, URL e SHA-256.

Prezzi: **136 VALID, 9 DEGRADED, nessun MISSING**. Otto FX e VIX non superano i controlli OHLC/calendario e restano esclusi dal ranking. **125 ETF/ETP eleggibili al solo ranking tecnico**; indici benchmark e rischio non sono candidati operativi. Il provider ha restituito `USDCAD=X` per l'alias `CAD=X`: registry corretta al canonico e nuova acquisizione diretta verificata, senza inversione valutaria.

Yahoo Finance è una fonte indicativa unica: hash e controlli interni non equivalgono a riconciliazione indipendente o certificazione dei dividendi. I due anni di storia non dimostrano ATH. Macro FRED DEGRADED: valori reali rivisti, disponibilità delle vintages non qualificata; nessun uso nel ranking/backtest.

## Test

- **57 test Intelligence passati**, Python 3.14 e Streamlit 1.56.0 nel runtime esistente.
- **119 test e 16 subtest Core passati su copia isolata**. Un primo tentativo sull'originale è stato fermato dal sandbox quando un test ha tentato di scrivere un artifact di audit; suite quindi rieseguita sulla copia.
- Formule verificate con attesi indipendenti; RVOL esclude la seduta corrente dalla base. Controllati volume assente/zero/negativo, hash alterato, sintetici, staleness, duplicati, mismatch simbolo, esclusione seduta corrente, disponibilità as-of, UTC, seduta interna saltata e calendario, confronto senza fill, macro obsoleta/non finita/mese mancante, Core assente/schema nullo/symlink escaping, DB corrotto e letture prive di scritture, shortlist max10, API GET-only e benchmark escluso dal ranking.
- UI: sei viste, fonti e grafici, filtri vuoti, fonti assenti, orizzonti/delta coerenti e SYNTHETIC escluso anche con flag eligible errato. La home include Top Opportunities (massimo 10), ordinamento per prontezza/score, drill-down, esclusione dati degradati e gate di ingresso fail-closed.
- AppTest su dati reali: Overview 1 grafico, explorer 2, flows 1, macro/bond 1, monitor e qualità con tabelle/stati. Nessuna eccezione.
- TestClient sullo snapshot reale: `GET /research/v1/state`, HTTP 200 e 145 record schema 1. Non richiede un server TCP.
- Fix legacy: test qualità ora genera valori in base alla lunghezza effettiva di `bdate_range` anche a fine settimana. Nessun modello finanziario cambiato.

## Gate finanziari invariati

SPY Core: 1.819 barre, 1.189 volumi mancanti, BLOCKED e nessuna performance economica calcolata. Fixture ENGINEERING_ONLY. Phase 1 aperta e Phase 2 incompleta.

Demo PARTIAL_NOT_VALIDATED: freeze contabile e snapshot successivo restano distinti; residui e completezza dello storico irrisolti. Il monitor non espone saldi, P/L, esposizioni o identificativi personali e non promuove alcun gate.

## Verifica browser

La nuova homepage è stata verificata in Streamlit nel browser locale: rendering desktop, cambio orizzonte 1/3/12 mesi, Top Opportunities, drill-down, fonte, livelli tecnici e messaggio di blocco del gate Phase 2. La porta `8517` era già occupata da una copia preesistente della dashboard; la verifica della versione aggiornata è stata quindi eseguita temporaneamente su `127.0.0.1:8518`, poi arrestata. Nessun server è stato lasciato attivo.

Dal normale Terminale del Mac: `bash scripts/start_dashboard.sh` nella cartella del checkout, poi aprire `http://127.0.0.1:8517`. Se la porta è occupata, usare `INTELLIGENCE_PORT=8518 bash scripts/start_dashboard.sh` e aprire `http://127.0.0.1:8518`.

Flussi ETF, COT/OI, fondamentali, duration/carry, Flow–Price Divergence preregistrato, news verificate e ranking multifattoriale calibrato restano incrementi 2–3. Nessun execution gateway o agente finanziario autonomo.
