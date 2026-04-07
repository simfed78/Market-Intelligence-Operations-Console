# Local Setup

1. Create the environment:
   `bash scripts/bootstrap_local.sh`
2. Copy `.env.example` to `.env` if you want to add optional keys such as `FRED_API_KEY`.
3. Run a first daily cycle:
   `.venv/bin/python -m src.main --mode daily --project-root .`

The local SQLite database is created at `data/db/market_intelligence.db`.
Exports land in `outputs/exports/`.
