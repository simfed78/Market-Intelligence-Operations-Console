# Phase 2B — Multi-Asset Intelligence MVP

## Avvio sul Mac

Questo checkout usa il branch `phase2b/dashboard-mvp`; gli originali del Core e di Market Intelligence rimangono separati.

Dal Terminale, entra nella cartella che contiene questo documento e `streamlit_app.py`, quindi:

```bash
bash scripts/start_dashboard.sh
```

Apri **http://127.0.0.1:8517**. Arresta con Ctrl+C. La dashboard legge gli snapshot locali: non scarica dati all'apertura e non esegue workflow legacy. Il pulsante **Rileggi snapshot** ricarica la vista; non interroga le fonti.

Il launcher sceglie, in ordine: `INTELLIGENCE_PYTHON`, `.venv/bin/python`, il percorso locale ignorato da Git in `.runtime-python`, `python3`. Sul Mac corrente `.runtime-python` riusa il virtualenv già installato nel progetto Market Intelligence originale; non lo modifica. Questo file non è distribuito nel repository.

Per un ambiente indipendente o un altro Mac:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash scripts/start_dashboard.sh
```

Non servono chiavi OpenAI, credenziali eToro o chiavi FRED per questo MVP. È possibile scegliere un altro runtime/porta:

```bash
INTELLIGENCE_PYTHON="/percorso/venv/bin/python" INTELLIGENCE_PORT=8518 bash scripts/start_dashboard.sh
```

## Aggiornamento esplicito

```bash
bash scripts/refresh_intelligence.sh
```

Il comando acquisisce i 145 strumenti e le otto serie macro con concorrenza limitata. Registra esiti e hash in `data/db/intelligence_v1.sqlite`, separato dal vecchio database. Poi premi **Rileggi snapshot** nella dashboard. Se una fonte fallisce, la versione precedente resta conservata; le date di osservazione, disponibilità e acquisizione e gli errori del run rimangono visibili. Una serie obsoleta non entra nel ranking.

La connessione Internet del Terminale deve raggiungere Yahoo Finance e FRED. In questa sessione di sviluppo il download è stato eseguito attraverso il runtime con accesso rete e gli stessi payload originali sono stati importati con:

```bash
bash scripts/refresh_intelligence.sh --import-inbox data/intelligence_inbox
```

Questa seconda forma importa snapshot già acquisiti e **non aggiorna** i dati. Non copiarvi fixture o dataset privi di provenienza. Il namespace della dashboard non legge mai cache, report o prezzi sintetici legacy.

## Viste disponibili

| Vista | Funzione disponibile | Limite esplicito |
|---|---|---|
| Overview | Performance, filtri, **Top Opportunities** (max 10), leader/debolezze tecniche, macro indicativa | Non è un ranking completo di valore/opportunità |
| Asset explorer | Prezzi, medie, volumi reali, confronto normalizzato, fonti | Drawdown dal massimo del campione di due anni, ATH assente |
| Capital flows | RVOL 5/20/60, z-score, OBV e CMF quando i campi sono validi | Non sono flussi netti ETF; nessuna inferenza istituzionale automatica |
| Macro & relative value | CPI/produzione USA, Treasury nominale/reale, breakeven, IG/HY OAS, NFCI e confronto equity/bond | Dati FRED rivisti, nessun ERP o term premium inventato |
| Trading Desk monitor | Artifact sanitizzati del Core, gate, blocchi SPY, stato Demo | Sola lettura, nessuna chiamata eToro |
| Data quality | Stato per asset/campo, timestamp, errori, export della vista filtrata | `VALID` significa controlli interni di ricerca, non certificazione economica |

L'universo distingue ETF, ETP, FX e benchmark non negoziabili. I nove benchmark azionari sono separati dagli ETF; gli indici e gli indicatori di rischio non entrano nella shortlist tecnica di opportunità. I proxy ETF quotati USA non sono automaticamente UCITS o negoziabili tramite il conto personale. Valuta di quotazione, esposizione valutaria e copertura sono concetti distinti. Costi, duration effettiva, liquidità e tracking error richiedono ancora dati emittente qualificati.

## Score e controlli

### Top Opportunities: coda di ricerca, non lista di acquisto

La home mostra una tabella **Top Opportunities** con al massimo dieci strumenti ordinati prima per prontezza tecnica (`research candidate`, poi `watch`) e quindi per momentum dell’orizzonte selezionato. I filtri globali di asset class e orizzonte si applicano anche a questa tabella. Ogni riga riporta ticker/nome, categoria, score e momentum, driver, qualità dell’attività-volume, qualità flow, rischio di volatilità, stato, motivo della priorità, livelli `close`/SMA50/SMA200 quando riproducibili, date e fonte. Il drill-down espone gli stessi elementi senza aggiungere informazioni non verificate.

- Entrano nella coda soltanto `price_status=VALID`, `ranking_eligible=true` e un momentum calcolabile. Serie `DEGRADED`, `MISSING` o `SYNTHETIC` non vengono promosse per riempire la tabella.
- `research candidate` significa solo priorità per ulteriore ricerca quando esistono prezzo valido, conferma tecnica completa e volume valido. `watch` segnala che uno di questi elementi non è completo. `blocked` è lo stato fail-closed per una valutazione non idonea; non è promosso nella Top 10.
- La colonna liquidità non deduce liquidità dai volumi: dichiara che bid-ask spread e ADV sono assenti e usa RVOL solo come proxy di attività. I flow ETF/COT sono `MISSING` finché non viene collegata una fonte dedicata.
- La valutazione “candidato d’ingresso” è possibile solo con dati tecnici e flow verificati e con tutti i gate Core esplicitamente aperti. Nel checkpoint attuale non appare alcun candidato: Phase 2 Core è `BLOCKED` e i flow sono assenti. Non viene usata la parola BUY.

- Momentum 1/3/12 mesi = `50 + 50*tanh(R_n / (s*sqrt(n/252)))`, con `n=21/63/252` sedute. Scale annuali fisse: equity 20%, bond 7%, commodity 25%, FX 10%. Indice tecnico descrittivo, non probabilità né rendimento atteso. Le scale sono ipotesi di progetto non calibrate.
- Conferma tecnica = 50 punti per prezzo sopra SMA50 + 50 punti per SMA50 sopra SMA200.
- Risk score = `100*min(1, volatilità annualizzata 63 sedute/(2*s))`. Misura solo volatilità storica relativa; non copre rischio credito, duration, liquidità o geopolitica.
- RVOL n = ultimo volume / media delle **n sedute precedenti**, escludendo l'osservazione corrente. Z-score usa media/deviazione standard delle 60 precedenti. OBV20 misura la somma dei volumi firmati dalla variazione di close; CMF20 usa OHLC realmente acquisiti. Nessun high/low o volume viene inventato.
- `opportunity_score`, valore relativo, carry, compatibilità macro, flussi ETF, COT/OI, POC e Flow–Price Divergence rimangono assenti dove non implementati. Non ripesiamo componenti mancanti per simulare un modello completo.
- Solo `ranking_eligible AND price_status=VALID` entra nella classifica tecnica. Le metriche di volume dipendono separatamente da `volume_status=VALID`. Nessuna pubblicazione di ranking operativo automatizzato.
- Controlli: hash, simbolo provider, OHLC positivi/finiti/coerenti, date univoche, copertura di almeno 253 sedute, freschezza e calendario USA per ETF/equity. Il calendario MVP è limitato al 2024–2027 e include la chiusura straordinaria del 9 gennaio 2025. Venue/anni sconosciuti vengono degradati; il calendario FX non è qualificato. Non è una certificazione dei timestamp open/close del Core.
- La barra della giornata corrente del fuso della borsa viene sempre esclusa, anche dopo la chiusura: conservativo, ultimo giorno pienamente trascorso. Nessun forward fill.
- `observed_at` è la data della seduta; `available_at` è la prima disponibilità dimostrabile dello snapshot, cioè l'acquisizione. La pubblicazione originale non è inferita. Gli snapshot sono conservati e le letture as-of non accettano acquisizioni future.
- Macro: nessun regime con CPI/INDPRO obsoleti, non finiti, non positivi o con mesi mancanti. Dati rivisti: contesto corrente DEGRADED, escluso dai ranking e dai backtest storici. Nessun fallback neutrale.
- Le letture del database usano SQLite `mode=ro`. Il salvataggio shortlist è l'unica scrittura disponibile nell'interfaccia; massimo 10 simboli dell'universo.

## Integrazione senza fusione dei repository

1. **Market Intelligence** resta proprietario di UI, registry, acquisizione e snapshot di ricerca. I vecchi moduli e test sono conservati; i workflow legacy sono esclusi dal nuovo entrypoint.
2. **Trading Desk Core** resta proprietario di motore, dataset certificabili, contabilità e qualificazione backtest. Nessun file originale è stato modificato.
3. **Contratto versionato**: SQLite `intelligence_v1.sqlite` è lo storage locale; `load_dashboard()` espone il modello Python; `GET /research/v1/state` espone JSON sanitizzato schema 1. Il Core potrà consumare snapshot immutabili senza usare i ranking per aggirare i gate di qualificazione.
4. Il monitor legge soltanto sei percorsi JSON allowlisted. Non importa script Core, non accede a broker, non mostra saldi, P/L, esposizioni o identificativi di conto/ordine/posizione. `TRADING_DESK_ROOT` può indicare un'altra cartella. Di default cerca `~/Documents/TRADING DESK`. Mancanza o schema inatteso degradano il relativo stato.
5. Il monitor Core è corrente e separato dalle eventuali viste storiche; non viene incluso nelle letture as-of.

API opzionale, soltanto locale:

```bash
.venv/bin/python -m uvicorn app_api.main:app --host 127.0.0.1 --port 8000
```

`GET /research/v1/state` è il contratto nuovo. Le vecchie route `/latest/*` e `/history/*` rimangono legacy, possono contenere risultati dimostrativi e **non sono fonti della nuova dashboard**. Non esporre nessuna di queste API su Internet.

## Roadmap e criteri successivi

| Incremento | Priorità | Criterio di accettazione |
|---|---|---|
| 1 | Dashboard autonoma | Streamlit, dati reali, filtri, grafici, ranking tecnico spiegabile, qualità e Core read-only; verifica browser HTTP ancora da effettuare fuori sandbox |
| 2 | Flussi e relative value | Fonti ETF flow/COT/OI con pubblicazione; dati fondamentali equity e duration/carry bond; specifica sperimentale FPD preregistrata e nessuna pretesa predittiva prima dei test |
| 3 | Ricerca quantitativa | Vintages storiche, universi point-in-time, walk-forward, costi, correlazioni/esposizioni e ranking multifattoriale calibrato per asset class |

Non sono stati aggiunti agenti finanziari LLM, execution gateway o accessi al portafoglio Real.

## Verifiche e limiti della consegna

Vedi [registro di verifica](phase2b_validation.md). La sessione non può aprire socket TCP locali: l'avvio HTTP ha restituito `PermissionError: Operation not permitted`. L'app è stata eseguita con Streamlit AppTest su dati reali e con fixture dichiarate nei soli test. Grafici e filtri risultano presenti nell'albero applicativo; **la resa grafica nel browser e l'effettivo avvio HTTP non sono stati verificati**. Il comando iniziale consente di completare questa verifica dal Terminale del Mac.

### Fonti metodologiche

- [NYSE: orari e calendari](https://www.nyse.com/markets/hours-calendars)
- [ICE: chiusura del 9 gennaio 2025](https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx)
- [FRED: revisioni e vintages ALFRED](https://www.stlouisfed.org/publications/page-one-economics/2022/08/01/data-revisions-with-fred)
- [ALFRED: disponibilità delle revisioni](https://alfred.stlouisfed.org/help)

I payload originali e gli URL esatti di acquisizione sono nel database locale, con hash SHA-256. I dati sono per ricerca personale indicativa; diritti di redistribuzione e uso automatizzato per execution/backtest Core non sono certificati.
