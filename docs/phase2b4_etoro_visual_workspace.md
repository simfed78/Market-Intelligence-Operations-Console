# Phase 2B.4 — eToro REAL risk workspace & visual dashboard

Status: changes must pass review, GitHub Actions tests and hosted Streamlit
deployment verification. This extends the original dashboard; no new app.

## User experience

The left sidebar and prominent top navigation include:
- **Overview**: redesigned responsive shell, stronger market signal hierarchy,
  top technical-score bar chart; old ranking facts and quality still available.
- **Fineco · Piano operativo**: existing buy-and-hold 12-month policy and
  explicitly confirmed EUR cash; now adds cash-allocation donut and world/gold/
  commodities signal cards. Up to three *new purchase* candidates.
- **eToro · Piano operativo**: separate REAL account risk cockpit, *no deposits*,
  no new broker orders. Current mark-to-market, cash, floating P/L, margin
  usage, leverage/short notional, risk actions, exposures and +2/+5/+10%
  shock scenarios for SPX500 (before costs), with a clearly hypothetical
  short exposure reduction slider.

All chart inputs are labeled: no fabricated time series, cash flows or
platform margin-call thresholds. A change in marked holding value is distinct
from leveraged gross exposure.

## eToro data boundary

ChatGPT's eToro plugin connection is **not** available inside the public
Streamlit Community Cloud server. The site must not request or store a user's
eToro OAuth token or API key, or fetch broker positions on behalf of visitors.

Instead, the owner uses ChatGPT's **read-only** eToro connection to export
a short-lived JSON file and deliberately imports it via the **session-only
file uploader**. The public repository, public GitHub Actions research-data
branch, cache and the application's database carry **no real account data**.

Only the session needs the normalized holdings/short positions. Uploading
the file to the public hosted app does transmit its account data to the
Streamlit server for processing. It is not uploaded anonymously to GitHub;
the site owner/server operator could theoretically access process memory.
The file must contain **no secrets, tokens, email addresses, banking IDs or
passwords**. The browser session may be lost after reset. Never share the
session URL as a way to export broker information.

### Versioned `etoro-private-snapshot.v1` contract

```json
{
  "schema_version":"etoro-private-snapshot.v1",
  "account":"real",
  "currency":"USD",
  "as_of":"2026-11-08T18:00:00+00:00",
  "totals":{
    "equity":5000,"available_cash":50,
    "used_margin":2500,"unrealized_pnl":-800
  },
  "holdings":[
    {
      "symbol":"SPX500","value":200,"exposure":-2500,
      "pnl":-700,"leverage":20,"position_count":1
    }
  ],
  "positions":[
    {
      "position_id":101,"symbol":"SPX500","direction":"short",
      "units":0.5,"current_rate":5000,"leverage":20,
      "pnl":-700,"stop_loss":5600
    }
  ],
  "pending_orders_count":0
}
```

The values above are **synthetic examples**, not an account snapshot.
The importer whitelists fields, rejects nonfinite numbers, a Demo account,
non-USD account, duplicate position IDs, and a reported SPX notional that
conflicts with units times current price by more than 2% / USD 30. It does
not deserialize account secrets and makes no HTTP broker requests.

An older-than-36-hour snapshot is labeled stale: action rows become
"AGGIORNARE DATI PRIMA DI AGIRE". Actual broker order costs and closing
permissions require a direct eToro preview/quote before the user independently
decides whether to act.

## Risk calculation

- `short_notional`: absolute broker-reported negative SPX500 exposure in USD.
- `short_to_equity = short_notional / equity`, when equity positive.
- Scenario +x% S&P 500: `-short_notional * x/100` assuming fixed sensitivity.
- Hypothetical short reduction r%: multiply scenario by `1-r/100`.
- Market-value allocation chart groups current holding values; the short
  notional is **not** added to mark-to-market asset values.
- `used_margin / equity` is diagnostic only, not broker free margin,
  liquidation threshold or available buying power.
- Stops may slip; cost of financing and stop gaps not modeled.
- Priority queue emphasizes concentrated SPX500 x20, daily-reset TMF and
  other leverage, before considering new positions.

## Validation and deployment

```bash
python -m pytest -q tests/test_etoro_planner.py \
  tests/test_intelligence_dashboard.py tests/test_fineco_planner.py
```

The GitHub Actions workflow covers these and prior Intelligence regressions.
After merging, Streamlit Cloud should serve branch `main` / entrypoint
`streamlit_app.py`. Confirm the header shows `2B.4-RISK-2026-11-08`
and the sidebar contains both separate broker sections. An iPhone visual
review and a user upload of a fresh private snapshot remain user-side checks;
test success alone does not establish a completed hosted deployment.
