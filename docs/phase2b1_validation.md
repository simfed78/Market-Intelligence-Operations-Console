# Phase 2B.1 — verification record

7 November 2026. Working branch: `phase2b1/actionable-opportunities`. Starting implementation: `66bd6f8`; pre-existing local Top Opportunities work preserved separately in `376164d` before changes.

## Implemented and tested

- Four horizons (1/3/6/12 months), class-specific technical composites, explicit ordinal within-class normalization, deterministic Top10 and ties.
- Named RESEARCH CANDIDATE / WATCHLIST / BLOCKED states. ENTRY CANDIDATE is reserved and never emitted without a validated entry model.
- Separate factors and quality states; absent macro/value/net-flow scores remain null. Missing inputs cannot enter operational ranking.
- Ranked history by model/run/horizon, prior-rank validity checks for unchanged coverage, and no historical rank fabrication.
- Public, source-backed names; category, observation/availability/acquisition dates, descriptive early/risk/volume evidence and technical levels.
- Homepage hierarchy, filters, sortable/selectable table and dropdown/button drill-through; six existing workspaces retained.
- Online cold-start public-data acquisition, refresh button, per-session public shortlist, Core disabled in public mode. No local database/account file is distributed.

## Automated results

**75 tests passed** in the complete Intelligence suite, including ranking order, ties, invalid sources, missing factors, horizons, filters, detail navigation, rank history and as-of, raw versus net flow distinctions, public Core isolation, per-session shortlist privacy and mocked public-source startup. Synthetic fixtures exist only inside tests and are explicitly identified.

The old orchestration engineering test depended on real Yahoo calls and two attempts stalled in `yfinance.multi.download`. These attempts were interrupted. The test now explicitly disables the live Yahoo adapter for that legacy orchestration check; the full deterministic suite passes. This change does not certify live data or alter Core tests.

Real-snapshot smoke check at run `2026-11-07T12:32:13.034392+00:00`: 153 imported sources, zero import errors; 145 instruments, 136 price VALID, 9 DEGRADED. No new download was implied by re-importing those original dated payloads. Three descriptive early signals; none is statistically validated as predictive.

AppTest exercised every real-data workspace without exception: Overview (1 graph, 7 tables), Asset explorer (2 graphs, 4 tables), Capital flows (1 graph), Macro/relative value (1 graph), Core monitor and Data quality. TestClient returned HTTP 200 for the full JSON contract, including 145 ranked/blocked records per horizon. These checks verify application execution and chart specification, not final browser rendering.

Core original files, reconciliation, backtest engine, qualification gates and order handling were not modified. The earlier Core test record remains separate; no Core test pass is asserted as a new validation of this opportunity model.

## Delivery and remaining limits

Publishing source to GitHub is separate from verifying the live Streamlit app. The known deployment configuration is repository `simfed78/Market-Intelligence-Operations-Console`, branch `main`, root `streamlit_app.py`. Browser transport became unavailable during this task, so the Community Cloud workspace and final live rendering could not be inspected. The verified legacy deep link returns the Streamlit web shell; HTTP 200 alone does not establish that the updated app is running. A live app URL must be observed or supplied before claiming online acceptance complete.

No fundamental/net-flow/COT source, statistical entry validation, point-in-time historical universe, return forecasts, walk-forward performance, or full cross-asset valuation model has been created. Opportunity Score measures technical rank position within a class, not expected return or absolute investment value. Cross-class ties have a deterministic display order, not stronger conviction.

Community Cloud runtime storage is ephemeral; past ranks may be unavailable after restart. Source outages result in unavailable/degraded signals; no synthetic fallback. The public monitor has no broker connection and does not reveal the local Core.

## Hosted/mobile correction after the user screenshot

The screenshot confirms the updated app is live at `https://market-intelligence-operations-console-7ejfn7tyabjcktlo7kdy22.streamlit.app`. It also shows 44/145 valid prices, missing macro, a generic outage warning and no completed-run caption. It does not prove the entire source set is unavailable.

Code review established two reproducible defects: a concurrent refresh returned acquired=0 and was mislabeled as an outage, and a cold reader could expose uncommitted partial snapshots. The correction separates RUNNING/COMPLETE/FAILED, runs source IO in a background worker, publishes completed runs only, and polls job status without rerunning source requests. Provider failures now include sanitized reason, HTTP status and Retry-After when available. Qualified recent payloads are reused; public requests are paced and new attempts stop after a 120-second job budget (active requests retain their existing timeout). No source rate limit is bypassed.

82 regression tests passed. New tests cover concurrent starts, exception state without automatic retry loops, redacted diagnostics, cold-run publication isolation, cache freshness/hash, exhausted acquisition budget, loading-state UI and compact-card navigation. The legacy market adapter engineering test now explicitly avoids live Yahoo IO, as the legacy orchestration test already does. This is not a certification of provider availability.

Real-snapshot AppTest in compact mode shows ten opportunity cards and no full-height macro metric cards. The user's screenshot is the evidence of the prior live rendering; the new mobile rendering has only been exercised through AppTest because browser automation remains unavailable. Full live Yahoo/FRED recovery is not claimed before actual server diagnostics show it.
