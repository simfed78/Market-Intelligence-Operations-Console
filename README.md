# Market Intelligence Engine

## Phase 2B.1 — opportunity discovery

Il nuovo entrypoint `streamlit_app.py` apre la dashboard di ricerca autonoma. Avvio: `bash scripts/start_dashboard.sh`. Aggiornamento: `bash scripts/refresh_intelligence.sh`. [Top10, metodologia e accesso online](docs/phase2b1_opportunities.md) · [Guida Phase 2B](docs/phase2b_dashboard.md). I workflow descritti sotto rimangono legacy e non alimentano la nuova dashboard.

Market Intelligence Engine is a local-first Python decision-support platform for SPX500 regime research, sector rotation, cyclical opportunity detection, proxy validation, and operational watchlist review.

Phase 4 keeps the system research-first:

- robustness over complexity
- transparency over black-box modeling
- no broker integration or live order routing
- persistent history for score and ranking changes
- operationally useful daily without hiding the logic

## Architecture Overview

- `src/data`: market, macro, event, earnings, options proxy, snapshots, and data-quality loaders
- `src/agents`: interpretable context, ranking, alerting, basket, and opportunity agents
- `src/models`: validation, structural breaks, exposure logic, portfolio research, and signal registry
- `src/storage`: SQLite-backed run history, scores, rankings, alerts, baskets, and transitions
- `src/orchestrator`: daily, weekly, and scheduler-friendly run workflows
- `src/reports`: markdown, JSON, CSV, HTML, and export helpers
- `app`: Streamlit operational console
- `app_api`: local FastAPI service layer

## Phase 2B.2 — read-only research export for weekly Fineco/eToro reports

The existing opportunity engine now has a proposed fail-closed, versioned
JSON publication workflow on a dedicated GitHub branch. The export contains
only derived research indicators, freshness and quality (never broker state),
so the Monday trading report can inspect the same model without scraping
Streamlit's UI. **An unreviewed branch or missing first Actions publication
is not a live data feed.** See [Phase 2B.2 integration guide](docs/phase2b2_research_export.md).

## Fineco · Piano operativo (Phase 2B.3)

Use the **Fineco · Piano operativo** sidebar section to translate the
existing global market indicators into a **fixed three-instrument new-buy
set**: VALL (global equity), PRAB (EUR 0–1Y government bonds), and SGLN
(physical-gold ETC). A separate session-private account-value input and
explicitly confirmed available cash are required before any indicative
amount is shown. U.S.-listed sector proxies never become automatic Fineco
buy orders. See [operating instructions](docs/phase2b3_fineco_workspace.md).

## Phase 2B.4 — eToro REAL risk cockpit and refreshed interface

The hosted Streamlit dashboard includes a distinct **eToro · Piano operativo**
workspace in the left navigation and a direct mobile link via `?etoro=1`.
It ingests only an explicitly **user-uploaded, short-lived, read-only**
`etoro-private-snapshot.v1` JSON; ChatGPT's eToro plugin credentials are
never transferred to or stored in the public hosting service. It charts
portfolio mark-to-market composition, leveraged SPX500 stress scenarios and
risk-priority actions. No orders, broker calls, transfers or automatic
trading are enabled. Fineco remains a separate EUR-funded buy-and-hold sleeve.

The dashboard visual system has been refreshed with mobile-responsive cards,
technical signal bars and clear priority/risk indicators. See
[Phase 2B.4 integration & privacy](docs/phase2b4_etoro_visual_workspace.md).

## Phase 4 Operational Additions

- persistent SQLite storage for runs, scores, rankings, alerts, baskets, and transitions
- historical score registry and what-changed summaries
- candidate basket engine and portfolio research summaries
- regime-based exposure overlay
- local scheduler-friendly shell scripts
- local API endpoints for latest and historical state
- operational dashboard pages for run history, baskets, exposure, alerts, and proxy health
- local deployment support with Docker, Compose, Make, and Streamlit config

## Data Sources And Assumptions

- `yfinance` for ETF and market proxy prices and volumes
- `fredapi` for FRED series when `FRED_API_KEY` is available
- local CSV fallbacks for manual sentiment, event, earnings, and options proxy inputs
- synthetic fallback data for offline verification and safe demos

Important assumptions:

- macro point-in-time handling is still partial
- correlations and lead-lag relationships are assumed unstable unless validation confirms otherwise
- seasonality, sentiment, event, and options context are contextual layers, not standalone trade triggers
- basket and exposure outputs are research overlays, not automated allocation advice

## Configuration

Primary config files:

- `config/settings.yaml`
- `config/weights.yaml`
- `config/validation.yaml`
- `config/proxy_registry.yaml`
- `config/macro_events.yaml`
- `config/earnings_map.yaml`
- `config/sector_constituents.yaml`
- `config/options_proxy.yaml`
- `config/opportunity_weights.yaml`
- `config/alerts.yaml`
- `config/baskets.yaml`
- `config/exposure_rules.yaml`
- `config/portfolio_research.yaml`

## Local Setup

```bash
cd market_intelligence_engine
bash scripts/bootstrap_local.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Daily And Weekly Runs

```bash
bash scripts/run_daily.sh
bash scripts/run_weekly.sh
```

Direct CLI:

```bash
.venv/bin/python -m src.main --mode daily --project-root .
.venv/bin/python -m src.main --mode weekly --project-root .
```

## Launch Dashboard And API

```bash
bash scripts/start_dashboard.sh
.venv/bin/uvicorn app_api.main:app --reload
```

Hosted Streamlit deployment:

- repo: `simfed78/Market-Intelligence-Operations-Console`
- branch: `main`
- main file path: `streamlit_app.py`

## Storage And Outputs

- SQLite database: `data/db/market_intelligence.db`
- latest payloads: `outputs/json/`
- reports: `outputs/reports/`
- tables: `outputs/tables/`
- workflow exports: `outputs/exports/`
- run logs: `logs/`

## API Endpoints

- `/health`
- `/latest/regime`
- `/latest/rankings/sectors`
- `/latest/rankings/cyclicals`
- `/latest/alerts`
- `/latest/baskets`
- `/history/scores`
- `/history/rank-transitions`
- `/history/runs`

## How To Extend

Add a new proxy:

1. add the symbol to `config/tickers.yaml` if it is market sourced
2. register it in `config/proxy_registry.yaml`
3. expose any new weights or exclusions in the relevant config

Add a new basket or exposure rule:

1. update `config/baskets.yaml` or `config/exposure_rules.yaml`
2. rerun the daily cycle
3. inspect the `Baskets` and `Exposure` dashboard pages

Add a new agent:

1. create the module in `src/agents`
2. wire it into `src/orchestrator/run_daily_cycle.py`
3. persist or expose the outputs if they matter operationally
4. add focused tests

## Docs

- [`docs/local_setup.md`](docs/local_setup.md)
- [`docs/daily_workflow.md`](docs/daily_workflow.md)
- [`docs/weekly_workflow.md`](docs/weekly_workflow.md)
- [`docs/dashboard_guide.md`](docs/dashboard_guide.md)
- [`docs/streamlit_deployment.md`](docs/streamlit_deployment.md)
- [`docs/troubleshooting.md`](docs/troubleshooting.md)
- [`docs/git_workflow.md`](docs/git_workflow.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Git Workflow

Recommended day-to-day flow:

```bash
git checkout main
git pull --ff-only
git checkout -b feature/short-description
make preflight
```

Helpful local commands:

- `make status`
- `make test`
- `make preflight`

The repository also includes:

- `.gitattributes` for line-ending normalization
- `.editorconfig` for consistent editing defaults
- PR and issue templates under `.github/`

## Known Limitations

- no full ALFRED publication-aware macro backfill yet
- constituent-level breadth remains partial and proxy-heavy
- offline fallback mode is useful for development, not for real research conclusions
- basket research is intentionally lightweight and does not model full transaction costs
- alert deduplication is state-based and local, not multi-user or distributed

## Recommended Next Step

Build a publication-aware historical state warehouse so regime, event, earnings, and opportunity transitions can be replayed on frozen information sets and reviewed against a fuller false-positive archive.
