# Phase 2B.2 — Scheduled derived research brief for Monday trading reports

Status: implementation on a review branch; **not production-ready until GitHub
Actions successfully publishes a real snapshot**. This extends the existing
Market Intelligence repository and does not modify the Trading Desk Core.

## Architecture and trust boundary

1. `src.intelligence.refresh` obtains public Yahoo/FRED market snapshots with
   request pacing. Existing provenance, hash, quality, calendar and as-of rules
   remain unchanged. Sources may fail; no synthetic replacement is permitted.
2. `src.intelligence.service.load_dashboard()` reads only the latest
   **completed** run. It uses the existing `technical-priority-v1` rankings;
   the export does not create any independent model.
3. `src.intelligence.report_export.build_brief()` enforces a recent completed
   run, at least one verified acquisition/cache, at least 70% VALID price
   coverage, and nonempty eligible research candidates in each horizon.
4. `python -m src.intelligence.report_export --root . --output ...` writes
   an atomic, source-limited JSON snapshot. On gate failure, nothing is
   published and the previous export is not overwritten.
5. `.github/workflows/research-brief.yml` runs on weekdays at **05:10 UTC**
   and on workflow updates to main. It validates tests first, acquires
   public market data, then pushes a *derived-only* publication to the
   **separate `research-data` branch**. No broker credentials are used.
6. The Monday assistant report reads exactly
   `exports/research/latest.json` from the `research-data` branch through
   the connected GitHub app and combines it with independently observed
   Fineco/eToro positions. It must never interpret research-only ranks as
   authorized orders.

### Publication URL

Once the first successful job has run:

`https://raw.githubusercontent.com/simfed78/Market-Intelligence-Operations-Console/research-data/exports/research/latest.json`

Or via the GitHub app, `fetch_file` with:
- `repository_full_name=simfed78/Market-Intelligence-Operations-Console`
- `path=exports/research/latest.json`
- `ref=research-data`

There is *no initial export* in Git: absence is deliberate, not fake data.

## Schema contract: `research-brief.v1`

- `schema_version`, `mode=RESEARCH_ONLY`,
  `publication_status=QUALIFIED_RESEARCH`
- `generated_at`: export-generation UTC timestamp
- `completed_run_at`: source-qualified completed run UTC timestamp
- `model_version=technical-priority-v1`
- `quality`: `price_valid`, `instruments_total`, `valid_ratio`,
  `source_errors`, `macro_status`
- `horizons`: `1m`, `3m`, `6m`, `12m`, each with `top10`,
  `leaders_by_asset_class` (up to 5 per class), and `eligible_count`.
- Allowed asset fields are an explicit allowlist: symbol, name, type,
  class, region/currency, research state, scores, relative strength,
  risk, timing, peer count, observation/retrieval timestamp and provider
  name. No raw OHLC, vendor response, source URL, client/account identifier,
  balance, order, position or execution state.

This brief is **not** an ETF recommendation and does not confirm UCITS,
availability on Fineco/eToro, spreads, costs, tax, expected return or
investment suitability. Cross-class `opportunity_score` is an ordinal,
within-class percentile, not a 12-month expected-return ranking.
`ENTRY CANDIDATE` is not emitted by the underlying model.

## Fail-closed consumer checklist for weekly reports

1. If the GitHub path is missing or unreadable, explicitly report dashboard
   data `UNAVAILABLE`; do not reconstruct rankings from memory.
2. Require exact schema `research-brief.v1`, `mode=RESEARCH_ONLY`,
   `model_version=technical-priority-v1`, and a nonfuture completed timestamp.
3. Require `generated_at` no older than **72 hours** for weekly reports;
   otherwise label the signal `STALE` and do not use it for transaction
   recommendations. For daily reviews use a tighter cutoff.
4. Verify source status, per-row `price_status=VALID` and
   `signal_state` in `RESEARCH CANDIDATE/WATCHLIST`; neither permits
   an immediate trade. Treat macro `MISSING/DEGRADED` as an explicit
   limitation, never a neutral vote.
5. Compare latest rank movements only if `rank_change` is present and
   the model/universe hashes match by existing engine rules.
6. Confirm tradability, instrument wrapper (UCITS ETF / gold ETC / US ETF /
   CFD), issuer facts, pricing, fees and instrument currency with independent
   qualified sources and broker ticket before any user-approved trade.
7. **Never** merge Fineco and eToro balances. Fineco monthly budget is
   1,000 EUR after the salary receipt, eToro budget is existing capital only.
8. No automatic broker calls or trade execution via this pipeline.

## Local manual operation and validation

```bash
python -m pip install -r requirements.txt
TRADING_DESK_PUBLIC=1 python -m pytest -q \
  tests/test_research_report_export.py tests/test_opportunities.py \
  tests/test_intelligence.py
TRADING_DESK_PUBLIC=1 python -m src.intelligence.refresh --root . \
  --request-interval 0.4 --budget-seconds 600
TRADING_DESK_PUBLIC=1 python -m src.intelligence.report_export \
  --root . --output /tmp/trading-desk-research-brief.json
```

The CLI uses completed runs only. The `--output` path should be local
or temporary: do **not** commit the SQLite database, raw downloads,
API keys or proprietary source series. GitHub Actions needs
`contents: write` permission to push `research-data`. If that permission
is blocked, fix repository Actions permissions; do not make the broker
account or the local FastAPI service public.

## Deployment verification required

- Review PR; validate GitHub Actions PR job tests.
- Merge after review; confirm one **successful** main-branch job.
- Check the published branch and fresh JSON `generated_at` / `quality`.
- Independently fetch the JSON from the account that runs Monday reports.
- Confirm the live Streamlit app is still accessible; do not infer a
  successful Streamlit deployment from GitHub publication.
- Keep `research-data` separate from the hosted UI's ephemeral SQLite.
  Both execute the same ranking code after merge but their independently
  downloaded sources may have different timestamps or coverage.
