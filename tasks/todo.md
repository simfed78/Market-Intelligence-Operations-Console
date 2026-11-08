# Phase 2B — dashboard first

## Scope and design
- Keep the Core and Intelligence codebases independent. No broker calls, no execution gateway.
- Reuse the existing Streamlit deployment, Plotly, Python configuration and repository. Extend with a strictly sourced data path: legacy cache provenance and invented OHLC/volume are unsuitable for this dashboard.
- Integrate Core only through a versioned allowlisted JSON reader. Never import Core scripts or alter qualification gates.
- Work on `phase2b/dashboard-mvp`, isolated clone of verified GitHub HEAD `5928d3404503a0b6ab797a62c598098e50c0d5cd`. Preserve the original uncommitted `_kpi_metric` helper in this clone.
- Data are local, ignored by Git. Use source snapshots + hashes, SQLite history, atomic imports and conservative availability dates. `VALID` means research input checks passed, not independent vendor certification or backtest readiness.

## Increment 1 acceptance
- [x] Audit both local projects and GitHub HEAD; preserve originals.
- [x] Registry of 100–150 instruments, distinct benchmarks/ETFs/FX.
- [x] Real sourced market snapshot, no synthetic fallback or forward filling.
- [x] Overview, interactive explorer/comparison, quality filters and technical ranking explanation.
- [x] Macro status and explicit gaps in full opportunity scoring.
- [x] Core monitor read-only with original financial gates preserved.
- [x] Meaningful unit/integration tests, regression suite, Streamlit AppTest checks.
- [ ] HTTP startup and rendered browser review outside the socket-restricted sandbox.
- [x] Exact Mac launch/refresh instructions and reviewed scope limitations.

## Next increments
2. Verified ETF creations/redemptions, COT and open interest; publication-aware equity/bond relative value; experimentally preregister Flow–Price Divergence before predictive testing.
3. Vintage-aware walk-forward and cross-asset multifactor calibration, overlapping exposures and portfolio research. No current-universe retrospective strategy performance.

## Risks and deliberate limitations
Yahoo is a single indicative research source, not an execution feed. Adjusted close is provider-adjusted, not a qualified dividend/payment ledger. Two-year drawdowns are sample drawdowns, not ATH. Live downloads can fail or be rate-limited: retain old snapshots and show freshness/failed-attempt diagnostics. FRED public CSVs contain revised history with no release vintage: use latest-state context only, never a historical causal backtest. US-listed ETF proxies are not presumed UCITS or personally tradeable.

## Review finale
56 test Intelligence + 119 test/16 subtest Core su copia; sei viste e API verificate con AppTest/TestClient su dati reali. 145 strumenti, 136 prezzi VALID, 9 DEGRADED, 125 ETF/ETP nel ranking tecnico. Avvio HTTP e verifica visiva browser non completati: bind TCP bloccato dal sandbox. Vedere docs/phase2b_validation.md.

## Phase 2B.1 — actionable research and online access
- [x] Audit current code and preserve pre-existing Top Opportunities changes.
- [x] Add horizon 6m, quality-gated relative strength/volume divergence, reproducible technical levels.
- [x] Pure ranking model with asset-class weights, within-class normalization, named signal states and no unvalidated ENTRY promotion.
- [x] Persistent versioned rank history; unknown previous ranks remain missing.
- [x] Homepage ordered macro, Top10, early radar, equity/bonds, vulnerabilities; click through to detail and shortlist.
- [ ] Publish source through GitHub and reuse the previous online dashboard service; never publish local Core/account data.
- [x] Unit, integration and regression checks; six real-data AppTest views and API.
- [ ] Rendered-browser verification: browser transport unavailable.
- [x] Commit and report exact launch/update/public URL and remaining limits.

## Hosted/mobile correction from user screenshot
- [x] Separate concurrent acquisition from actual outages and expose progress/errors.
- [x] Do not rank uncommitted first-run fragments.
- [x] Nonblocking first startup, bounded source pacing and reuse of fresh qualified snapshots.
- [x] Compact macro summary and readable mobile opportunity cards.
- [x] Regression tests and publish fix to existing Streamlit branch.

Hosted correction: 82 tests passed; mobile AppTest exposes 10 cards and zero macro metric cards. Server source availability must be checked from new diagnostics; no claim of 145 recovered sources.

## Phase 2B.2 — source-backed scheduled report integration
- [x] Discover and preserve existing GitHub/Streamlit source and ranking model.
- [x] Add research-only derived JSON contract and fail-closed freshness/coverage gates.
- [x] Add deterministic, security, stale-data and no-leak regression tests.
- [x] Add GitHub Actions PR validation plus weekday source refresh and separate data-branch publication.
- [x] Document weekly report consumer policy and strict Fineco/eToro data separation.
- [ ] Observe a successful PR CI run and review source/network errors.
- [ ] Merge approved PR and verify the first publication to research-data branch.
- [ ] Read the actual published JSON through the Monday-report GitHub connection.
- [ ] Verify live Streamlit remains working and compare run timestamps/coverage.

## Phase 2B.3 — Fineco limited-universe operational workspace
- [x] Reuse existing Streamlit and last completed research ranking; no new prototype.
- [x] Add Fineco sidebar with session-only portfolio input, after-salary cash confirmation and three-core buy candidates.
- [x] Add US-proxy vs EU-wrapper distinctions and commodity context without sector proliferation.
- [x] Fail closed for old/missing market data, missing cash, no broker prices, excessive concentration or small orders.
- [x] Add pure offline tests, AppTest check and CI validation workflow.
- [ ] Review PR test output and merge only after code checks succeed.
- [ ] Verify live hosted dashboard deploy, UI and input privacy on iPhone.

## Phase 2B.4 — eToro and dashboard visual refresh
- [x] Add independent read-only eToro REAL workspace and separate Fineco capital.
- [x] Support session-only user snapshot upload; never expose API credentials or broker data to public exports.
- [x] Add validated concentration/stress model and SPX500 reduction scenario.
- [x] Modernize color, navigation, responsive metrics and market-signal visualizations.
- [x] Add asset-allocation, stress, prioritized actions and per-broker signal cards.
- [x] Add synthetic tests and CI integration.
- [ ] Observe green CI, review and merge main-branch PR.
- [ ] Verify new public Streamlit release in Safari/iPhone and test a real private snapshot import.
