# Phase 2B.5 — Opportunity decision cards

The Overview defaults to responsive cards (three desktop columns, stacked on
small screens). Uncheck **Vista compatta** to use the sortable ranking table.
Both presentations consume the same Top 10 and filters; ranking and weights
are unchanged. Each card opens the existing Asset explorer.

Cards expose the qualified price, 60-session adjusted-price sparkline, technical
score, within-class opportunity percentile, rank delta, horizon and volatility
risk. Expand **Conferme, rischi e fonti** for source timestamps, quality, included
factors and descriptive confirmation/invalidation conditions.

Trend uses qualified price relative to existing SMA50/SMA200. Momentum compares
the 21-session return with the compounded monthly average of the 63-session
return. Extension is percentage distance to SMA50, without an oversold label.
Confirmation references existing prior-20-session resistance and moving averages;
invalidation references prior-20-session support. These describe a trend hypothesis,
not validated entry/exit rules or operational stops. Missing/non-VALID inputs
remain unavailable. Volume anomalies are explicitly distinct from net flows.
No gamma, institutional positioning, new BUY signals or broker actions are added.

Validation: full pytest suite, 134 tests passing; Streamlit AppTest covers cards,
table parity, missing factors, exclusion of invalid candidates and detail navigation.
Real account files, tokens and balances are excluded from this change.

Run on Mac from the repository:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run streamlit_app.py
```

Cloud entry point remains `streamlit_app.py`, deployment branch `main`.
Release label: `2B.5-CARDS-2026-11-20`.
