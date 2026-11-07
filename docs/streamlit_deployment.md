# Online deployment — Phase 2B.1

Repository: `simfed78/Market-Intelligence-Operations-Console`
Branch: `main`
Entrypoint: `streamlit_app.py`

The same Community Cloud app connected to this branch should rebuild after its source updates. If it is not already connected, configure these three fields at https://share.streamlit.io/ and deploy. Do not add broker credentials or copy a local database. An existing app URL must be read from the Community Cloud workspace; it cannot be inferred reliably from the repository name.

No API key is needed for the public Yahoo chart/FRED CSV adapters. Configure `TRADING_DESK_PUBLIC=1` to explicitly disable Core reads on any platform; Linux without a configured Core root is public by default. Public shortlists use per-visitor Streamlit session state. Mac local use retains the original sanitized, read-only Core monitor.

First online startup downloads public data only. Subsequent updates use **Aggiorna dati pubblici**. A failed request leaves previous snapshots intact and visible with source timestamps and quality. No sample/synthetic fallback exists in the new entrypoint. Runtime storage is ephemeral; rank changes are unavailable until compatible prior runs exist.

See [model, methodology and operating guide](phase2b1_opportunities.md). Publishing code is separate from verifying the live page; the live URL and rendered check must be recorded in the handoff.
