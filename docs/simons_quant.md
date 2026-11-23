# Simons Quantitative Evidence Gate v1

## Status

Research prototype on a separate GitHub branch. It is not yet connected
to the public Streamlit dashboard and cannot authorize purchases.

This reuses the existing qualified data pipeline:
1. The existing refresh process acquires daily Yahoo OHLCV chart JSON.
2. The existing Store persists source URLs, timestamps and SHA-256 hashes.
3. The existing normalize function checks the snapshot hash, dates, OHLC
   consistency, session coverage, age and volume completeness.
4. The new Simons module reads those already acquired bars and applies a
   repeatable walk-forward research evaluation.
5. Only a local JSON research report is produced. No broker credentials,
   portfolio values, trading API or private positions are accessed.

## Running the research on real existing snapshots

From the repository root, with Python requirements already installed:

    python -m src.intelligence.refresh --root .
    python -m scripts.simons_quant_research --root . --symbols SPY QQQ XLV XLE GLD TLT

To inspect the implementation without a data connection:

    python -m pytest -q tests/test_simons_quant.py

An optional more conservative transaction cost assumption is set with
--fee-bps 20 (default 10 one-way basis points).

Output: outputs/research/simons_quant_v1.json
Do not commit generated research outputs or broker snapshots.

If there are no qualified market snapshots, the result is NO_SNAPSHOT
or UNQUALIFIED_SOURCE, not a simulated signal.

## Pre-registered walk-forward design

- Inputs: adjusted daily OHLCV from already qualified market cache.
- Fixed candidate A: adjusted close > 100-day mean and > close 63 days ago.
- Fixed candidate B: 5-day decline > 4% while above 200-day mean.
- A decision made after close(t-1) is implemented no earlier than open(t).
- Strategy return: adjusted open(t) to adjusted open(t+1), net of assumed
  trading costs on one-way absolute changes in portfolio exposure.
- Warmup 200 trading days; 126-session training window; 2-session embargo;
  42-session testing window; at least four independent test folds.
- Between the two candidates, select based on Sharpe only using the
  preceding training fold, not the following test returns.
- Report net out-of-sample return, passive benchmark on the same test dates,
  excess return, Sharpe, maximum drawdown, per-fold selected model,
  exposure, block-bootstrap interval for arithmetic annualized excess mean.
- Never output a manufactured win probability or future return forecast.

## Critical limitations

Yahoo adjusted bars are an ex-post reconstruction and may change after
corporate actions: they are not certified point-in-time histories.
Yahoo 2-year acquisition windows may not provide enough observations
for four valid folds. Two signals are too small a search space to claim
discovery of a profitable generalizable strategy. Screening many symbols
raises multiple-comparison and selection-bias problems. Cost estimates
are assumptions, not verified eToro/Fineco fills. The passive comparison
is asset-specific, not beta-matched. Bootstrap intervals are diagnostics,
not proof of true alpha. Historical index membership and fundamental
publication vintages are not established. The test may not find a strategy
that trades often enough; abstention is the expected valid outcome.

## Before any production use

- Expand to 5-10 years of legally accessible historical prices with
  verified corrections and acquisition timestamps.
- Add a data-source audit and a stable as-of universe registry.
- Add independent market/sector benchmark comparisons and multiple-testing
  corrections before promoting any signal.
- Lock hypotheses before running long-horizon holdout tests.
- Run paper-trading forward and verify cost and slippage.
- Add Simons as an independent evidence auditor, not as a BUY vote.
- Preserve all existing Risk Officer and Portfolio read-only gates.

The Phase 3 dashboard, Committee and portfolio workspaces remain unchanged.
