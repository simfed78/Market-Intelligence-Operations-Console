# Phase 3A — Investment Decision Cockpit (development branch)

## Baseline and scope, 2026-11-22

- Remote source: simfed78/Market-Intelligence-Operations-Console, base
  `main` at `18b2be6f4d26a9e1a7d00e13943f1db12c0f5528`.
- Deployment entrypoint remains `streamlit_app.py` -> `app.intelligence_dashboard.main`.
- Existing ranking `src/intelligence/opportunities.py`, Yahoo snapshot
  hash/calendars/freshness `src/intelligence/market.py`, FRED context
  `src/intelligence/macro.py`, Fineco and eToro workspaces are reused unchanged.
- Separate *local* Trading Desk Core Phase 2.4B and AGENTS.md could not be
  accessed from this execution environment. No claim of its test baseline
  or of Core/Phase 2.4B integration is made.
- No real-account portfolio JSON, private balances or broker credentials
  have been fetched, stored, committed or merged into the public UI.

## Implemented

- `src/intelligence/phase3_committee.py`: independent Druckenmiller,
  Livermore, Burry and Buffett assessments; explicit abstention;
  a pure, assumption-limited DCF helper; deterministic Committee and Risk
  Officer veto policy. No invented macro probabilities or fundamental values.
- The macro engine reads existing revised FRED context. Under the current
  `DEGRADED` historical-vintage contract it **abstains** from entry approval.
- Livermore reads qualified technical structure, but current execution/stop
  validation is `MISSING`, so BUY NOW is **not** authorized by momentum.
- Burry and Buffett abstain on ETF/bond/commodity/FX instruments and on
  corporate instruments without verified, timely fundamentals. Corporate
  estimators require explicit source/dated inputs and expose limitations.
- Risk Officer blocks an entry for invalid/stale prices, missing validated
  entry model, unsupported securities, missing portfolio/broker data,
  leverage above 1x, unverified correlation, FX and liquidity checks, or
  concentration above 10%. No default position size is invented.
- UI: responsive max-three decision cards on Overview, deterministic action
  and readiness columns on the existing Top 10, dedicated Committee and
  four engine views, dark terminal styling. Other menu sections preserved.
- GitHub Actions regression workflow added for compilation, all tests,
  Streamlit health endpoint. Synthetic, labelled fixtures validate policies.

## Important conservative behavior

BUY NOW can only occur when: technical structure is constructive, at least
two *applicable, independent* engines are constructive, the explicit
`entry_validation == VALIDATED` gate is satisfied, and the Risk Officer
passes all market-data and portfolio checks. Today's sources do not establish
all those gates. The expected default is WAIT, AVOID or NO TRADE, not
fabricated recommendations.

Historical price rank is technical attractiveness, not entry readiness,
expected return or statistically calibrated investment probability.
Observed support/resistance is **not** a validated stop or broker order.
Any DCF output is an estimate, not an independently certified fair value.

## Unfinished and blocked by missing resources

1. No local Core/Phase 2.4B source reconciliation, baseline test or
   SPX options/Expected Move integration yet.
2. No historical vintage market/macro backtest, point-in-time company
   fundamentals provider, analyst revisions, durable market-state journal or
   walk-forward strategy validation.
3. No broker availability verification, UCITS/share-class identifiers,
   EUR/USD verified conversion or live position sizing. Fineco/eToro accounts
   remain separate in their original panels; the public Committee sees
   `DATA UNAVAILABLE` for portfolio effects.
4. No production deployment until CI, baseline regression and mobile
   rendering are verified. Publishing `main` is a separate guarded step.
5. No automatic orders; `RESEARCH_ONLY` throughout.

## Validation and release

- New test suite: `tests/test_phase3_committee.py`.
- PR workflow: `.github/workflows/phase3-ci.yml`.
- Run locally: `python -m pip install -r requirements.txt && python -m pytest -q`.
- Smoke: `streamlit run streamlit_app.py --server.headless true`.
- For release, reconcile local Core separately and test baseline compatibility.
- Review pull request, check all CI jobs, verify iPhone AppTest/real-browser
  rendering (not equivalent to CSS inspection), merge only after sign-off,
  then verify Streamlit Cloud commit/version and data-quality flags.

## Decision contract

Every decision has `model_version`, stable snapshot-dependent ID, source,
timestamp, four engine states/evidence/missing data/confidence, risk blockers,
readiness and recommended no-trade/trade action. The deterministic policy
does **not** average engine scores. Outputs are never execution instructions.
