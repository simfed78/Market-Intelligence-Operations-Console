# Troubleshooting

## No live market data

If Yahoo or FRED access is unavailable, the engine falls back to cached or synthetic data when configured to do so. Check:
- `outputs/reports/daily_report.md`
- `outputs/json/daily_payload.json`
- `logs/`

## Dashboard shows no data

Run a daily cycle first. The dashboard reads the latest payload and SQLite history.

## SQLite history is empty

Confirm the database exists at `data/db/market_intelligence.db` and that at least one run completed without crashing.

## API returns empty tables

The API is read-only. It depends on the same payload and SQLite artifacts as the dashboard.
