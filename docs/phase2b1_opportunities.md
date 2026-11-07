# Phase 2B.1 — Investment Opportunity Discovery

## Aprire e aggiornare

Sul Mac, dalla cartella del checkout:

```bash
bash scripts/start_dashboard.sh
```

Aprire `http://127.0.0.1:8517`. Aggiornare con **Aggiorna dati pubblici** nella sidebar oppure:

```bash
bash scripts/refresh_intelligence.sh
```

La pagina mostra separatamente ultima seduta e acquisizione. La prima registrazione del nuovo modello non ha un rango precedente: il delta resta mancante. Non ricostruiamo uno storico di ranking mai osservato.

## Homepage

1. Global Macro & Risk Regime.
2. Top 10 Multi-Asset Opportunities, ordinabile; selezione riga e pulsante di accesso alla scheda completa.
3. Emerging Opportunities / Capital Flow Radar.
4. Equity vs Bonds Relative Value.
5. Market Risk & Vulnerabilities.

Filtri per asset class, area, orizzonte 1/3/6/12 mesi, rischio di volatilità, stato, Early Opportunity, ricerca e shortlist. I filtri non ricalcolano i punteggi. La tabella presenta priorità 1–10 nel filtro e delta del rango globale. Tutte le sei viste precedenti restano disponibili.

## Che cosa significa Opportunity Score

Il modello `technical-priority-v1` è un **ordinatore tecnico di ricerca**, non un modello di fair value o rendimento atteso. Non è stato calibrato su performance future. Non usa informazioni del portafoglio.

Technical Score: somma pesata dei quattro indici di momentum della Phase 2B. Ogni componente deve esistere ed essere compresa fra 0 e 100. Pesi diversi per asset class e orizzonte sono dichiarati in `src/intelligence/opportunities.py::WEIGHTS`; nessuna ottimizzazione retrospettiva. È richiesta una classificazione di prezzo VALID, idoneità tecnica, strumento ETF/ETP/FX, rischio finito 0–100 e conferma tecnica in {0,50,100}.

Opportunity Score = `100 × (rango medio del Technical Score entro asset class − 1)/(numero peer validi − 1)`, con almeno tre peer. La normalizzazione rende confrontabile **il posizionamento relativo**; non rende confrontabili convenienza assoluta, premi per il rischio, volatilità economica o rendimento atteso. Il migliore di ciascuna classe può valere 100 pur avendo prospettive molto diverse. È una politica di selezione della coda di ricerca, non una classifica di investimento ottimale.

Ordinamento: percentile decrescente, asset class e ticker per gli ex aequo. La priorità 1–10 non è un peso di portafoglio. Nessun premio artificiale è attribuito ai dati di volume mancanti. Regime macro, valutazioni, carry e flussi netti restano separati e non ricevono un 50 neutrale.

Gli indici benchmark cash/performance e gli indicatori di rischio non sono candidati negoziabili; sono consultabili nell'explorer. Nessuna selezione di singole azioni è stata introdotta.

## Stati

| Stato | Regola attuale |
|---|---|
| RESEARCH CANDIDATE | Dati essenziali validi, almeno tre peer, Technical Score ≥60 e conferma ≥50 |
| WATCHLIST | Dati sufficienti ma condizioni tecniche non soddisfatte |
| BLOCKED | Dati/metriche essenziali non validi, benchmark non negoziabile o peer insufficienti |
| ENTRY CANDIDATE | Riservato a un modello di ingresso validato; mai emesso dalla versione corrente |

L'apertura di un gate del Core non certifica questo nuovo modello. La conferma di una media o di un breakout non autorizza un ingresso. Nessun ordine, accesso Real o execution gateway.

## Radar sperimentale

- RVOL: volume corrente / media delle precedenti sedute, senza includere la seduta corrente nella base.
- Price–volume divergence descrittiva: movimento a 21 sedute entro un limite per classe, OBV20 e CMF20 positivi.
- Forza relativa: rendimento del rapporto asset/benchmark su 21 e 63 sedute comuni; miglioramento = RS63 corrente meno RS63 osservata 21 sedute prima. Solo con benchmark e asset VALID, senza forward fill.
- Early Opportunity: prezzo ancora entro ±5% equity, ±2% bond, ±7% commodity o ±3% FX a 21 sedute; RVOL20 ≥1,2; OBV20>0; CMF20>0; miglioramento RS63>0. Richiede tutti i dati. Regola descrittiva fissa non ottimizzata, predittività da validare successivamente.
- Volume anomalo: RVOL20≥1,5 oppure z-score60≥2. OBV/CMF concordi sono indicati come accumulo **potenziale** con conferme tecniche; non provano flussi netti, acquisti istituzionali o identità degli operatori.
- ETF net flows, COT/open interest e volume profile/POC rimangono MISSING. La rotazione settoriale è ispezionabile dai ranking delle classi/sottocategorie e dai delta, non da flussi attribuiti artificialmente.

## Scheda asset

Nome completo da metadati provider ove disponibile, prezzi/medie, momentum su quattro orizzonti, drawdown del campione (non ATH), RS e benchmark, anomalie volume, fattori inclusi/esclusi, regime macro, rischi e condizioni di revisione.

SMA50/SMA200 derivano dai prezzi rettificati, riscalati alla chiusura corrente per esprimere livelli nella quotazione attuale. Supporto e resistenza sono minimo/massimo delle precedenti 20 sedute, escludendo l'ultima. Breakout è una descrizione della chiusura rispetto alla resistenza precedente, non una previsione. Nessun target, stop o probabilità di successo inventata.

Rischio basso/medio/alto usa lo score di volatilità della Phase 2B (soglie 25 e 50): non incorpora credito, duration, liquidità o rischio geopolitico. Questi limiti restano visibili. ETF USA non sono automaticamente UCITS o negoziabili nel conto personale.

## Integrità e storia

`opportunity_history` conserva record versionati per run, orizzonte, modello e simbolo. Il delta è disponibile solo quando coincidono modello, orizzonte, copertura globale e peer della classe. I dati di una fonte in corso di aggiornamento non vengono usati dalla dashboard prima del completamento del run. Il refresh può calcolare i dati non ancora pubblicati internamente, poi registra il run completato.

Le query as-of non ricevono snapshot, run o ranking futuri. Nessuna simulazione retrospettiva su questo universo corrente è descritta come backtest point-in-time. Il Core è letto soltanto tramite il monitor originale e rimane separato.

## Modalità online

Stesso repository e entrypoint della precedente Streamlit Community Cloud: branch `main`, `streamlit_app.py`. Al primo avvio online, se non esiste alcun run, vengono richiesti i soli dati pubblici alle fonti. Nessun database locale, `.env`, credenziale o artifact Demo deve essere pubblicato.

Su host Linux senza Core configurato, o con `TRADING_DESK_PUBLIC=1`, il monitor Core è disabilitato. Nella versione pubblica la shortlist è privata della sessione browser, non salvata in una preferenza condivisa fra visitatori. Il pulsante di aggiornamento usa un lock di processo; se un refresh è già attivo, non ne avvia un secondo.

Se Yahoo/FRED non rispondono, la pagina resta navigabile e mostra MISSING/DEGRADED e gli errori; non genera dati sostitutivi. Il filesystem di Community Cloud è effimero: dopo riavvio può essere necessario ricostruire gli snapshot e lo storico dei ranghi può ripartire senza confronti. Nessun servizio di trading viene esposto.
