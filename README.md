# Market Intelligence Engine

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
- [`docs/troubleshooting.md`](docs/troubleshooting.md)

## Known Limitations

- no full ALFRED publication-aware macro backfill yet
- constituent-level breadth remains partial and proxy-heavy
- offline fallback mode is useful for development, not for real research conclusions
- basket research is intentionally lightweight and does not model full transaction costs
- alert deduplication is state-based and local, not multi-user or distributed

## Recommended Next Step

Build a publication-aware historical state warehouse so regime, event, earnings, and opportunity transitions can be replayed on frozen information sets and reviewed against a fuller false-positive archive.
