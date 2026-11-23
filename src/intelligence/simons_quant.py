"""Simons-style quantitative evidence gate. Research only, never authorizes trades.

Consumes only already acquired, hash-verified Yahoo OHLCV snapshots normalized by
src.intelligence.market. No synthetic fallback, broker data, API secrets, or live orders.
Methodology is deliberately transparent, pre-registered, and point-in-time cautious.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from src.intelligence.market import normalize
from src.intelligence.store import Store

VERSION = "simons-quant-evidence-v1"
WARMUP = 200
TRAIN = 126
TEST = 42
EMBARGO = 2
MIN_FOLDS = 4
STRATEGIES = ("trend_100_63", "pullback_5_200")


def _utc(value):
    try:
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is None:
            return None
        return stamp.tz_convert("UTC")
    except (TypeError, ValueError, OverflowError):
        return None


def _abstain(symbol, code, reason, **context):
    return {"symbol": symbol, "model_version": VERSION, "status": code,
            "decision": "ABSTAIN", "reason": reason, "folds": [],
            "trade_authorized": False, **context}


def _sharpe(series):
    values = np.asarray(series, dtype=float)
    if len(values) < 20 or not np.isfinite(values).all():
        return None
    std = np.std(values, ddof=1)
    return float(np.mean(values) / std * np.sqrt(252)) if std > 1e-12 else None


def _max_drawdown(returns):
    equity = np.cumprod(1 + np.asarray(returns, dtype=float))
    if len(equity) == 0:
        return None
    peaks = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    return float(np.min(equity / peaks - 1))


def _block_ci(alpha, seed=1701, block=5, n_boot=1000):
    """Block-bootstrap CI for annualized *arithmetic* alpha, not a success probability."""
    a = np.asarray(alpha, dtype=float)
    if len(a) < 80 or not np.isfinite(a).all():
        return None
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, len(a) - block + 1))
    means = []
    for _ in range(n_boot):
        picks = rng.choice(starts, size=int(np.ceil(len(a) / block)), replace=True)
        sample = np.concatenate([a[k:k + block] for k in picks])[:len(a)]
        means.append(float(sample.mean() * 252))
    return [float(x) for x in np.quantile(means, [.025, .975])]


def evaluate_history(symbol, bars, meta, *, as_of, fee_bps=10.0):
    """Walk-forward select between TWO fixed rules using training data only.

    Positions at open(t) use signals computed at close(t-1). Returns measure
    adjusted-open(t)->adjusted-open(t+1), with one-way turnover cost at open(t).
    Historical adjusted prices are ex-post adjusted and therefore NOT a fully
    point-in-time, executable reconstruction.
    """
    stamp = _utc(as_of)
    if stamp is None:
        return _abstain(symbol, "INVALID_INPUT", "as_of must be timezone-aware")
    retrieved = _utc(meta.get("retrieved_at")) if isinstance(meta, dict) else None
    if (not isinstance(meta, dict) or meta.get("source") != "Yahoo Finance"
            or meta.get("price_status") != "VALID" or retrieved is None
            or retrieved > stamp or (stamp - retrieved).total_seconds() > 5 * 86400):
        return _abstain(symbol, "UNQUALIFIED_SOURCE", "Qualified recent source and acquisition timestamp required")
    if not np.isfinite(fee_bps) or not 0 <= fee_bps <= 100:
        return _abstain(symbol, "INVALID_INPUT", "Invalid one-way trading-cost assumption")
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    if not isinstance(bars, pd.DataFrame) or not required.issubset(bars.columns):
        return _abstain(symbol, "INVALID_BARS", "Missing OHLCV/adjustment fields")
    f = bars.copy().sort_values("date").reset_index(drop=True)
    f["date"] = pd.to_datetime(f["date"], errors="coerce")
    numeric = f[["open", "high", "low", "close", "adj_close"]].apply(pd.to_numeric, errors="coerce")
    if (f["date"].isna().any() or f["date"].duplicated().any()
            or numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all()
            or (numeric <= 0).any().any()
            or (numeric["high"] < numeric[["open", "close"]].max(axis=1)).any()
            or (numeric["low"] > numeric[["open", "close"]].min(axis=1)).any()):
        return _abstain(symbol, "INVALID_BARS", "Dates, adjustments or OHLC are inconsistent")
    if f["date"].iloc[-1].date() >= stamp.date():
        return _abstain(symbol, "FUTURE_BAR", "Use closed, prior-session bars only")
    if (stamp.date() - f["date"].iloc[-1].date()).days > 5:
        return _abstain(symbol, "STALE_BARS", "Historical data is no longer current")
    if len(f) < WARMUP + TRAIN + MIN_FOLDS * (TEST + EMBARGO) + 1:
        return _abstain(symbol, "INSUFFICIENT_HISTORY",
                        "Need at least 503 daily sessions for four independent test folds",
                        bars=len(f), min_bars=WARMUP + TRAIN + MIN_FOLDS * (TEST + EMBARGO) + 1)
    adjusted_close = numeric["adj_close"]
    adjusted_open = numeric["open"] * adjusted_close / numeric["close"]
    next_open_return = adjusted_open.shift(-1) / adjusted_open - 1
    if not np.isfinite(next_open_return.iloc[:-1]).all() or (next_open_return.iloc[:-1] <= -1).any():
        return _abstain(symbol, "INVALID_BARS", "Non-finite or impossible next-open return")
    rules = {
        "trend_100_63": ((adjusted_close > adjusted_close.rolling(100).mean())
                         & (adjusted_close > adjusted_close.shift(63))),
        "pullback_5_200": ((adjusted_close.pct_change(5) < -.04)
                           & (adjusted_close > adjusted_close.rolling(200).mean())),
    }
    costs = fee_bps / 10000
    performance = {}
    positions = {}
    for key, signal in rules.items():
        position = signal.shift(1, fill_value=False).astype(float)
        turnover = position.diff().abs().fillna(position.abs())
        returns = position * next_open_return - costs * turnover
        performance[key] = returns
        positions[key] = position
    fold_records = []
    oos, benchmark, oos_dates = [], [], []
    train_end = WARMUP + TRAIN
    while train_end + EMBARGO + TEST <= len(f) - 1:
        train_start = train_end - TRAIN
        test_start, test_end = train_end + EMBARGO, train_end + EMBARGO + TEST
        candidates = []
        for key in STRATEGIES:
            train_values = performance[key].iloc[train_start:train_end].to_numpy()
            s = _sharpe(train_values)
            # An inactive or constant strategy cannot win model selection.
            if s is not None and positions[key].iloc[train_start:train_end].sum() >= 5:
                candidates.append((s, key))
        if candidates:
            _, selected = max(candidates, key=lambda x: (x[0], x[1]))
            r = performance[selected].iloc[test_start:test_end].to_numpy()
            b = next_open_return.iloc[test_start:test_end].to_numpy()
            # Benchmark: buy-and-hold; explicit one-way initial cost for each fold.
            b = b.copy()
            b[0] -= costs
            fold_records.append({
                "start": str(f["date"].iloc[test_start].date()),
                "end": str(f["date"].iloc[test_end - 1].date()),
                "selected_on_training": selected,
                "train_sharpe": float(max(candidates)[0]),
                "test_return_net": float(np.prod(1 + r) - 1),
                "benchmark_return_net": float(np.prod(1 + b) - 1),
                "test_exposure": float(positions[selected].iloc[test_start:test_end].mean()),
            })
            oos.extend(r.tolist())
            benchmark.extend(b.tolist())
            oos_dates.extend(f["date"].iloc[test_start:test_end].dt.date.astype(str).tolist())
        train_end = test_end
    if len(fold_records) < MIN_FOLDS:
        return _abstain(symbol, "INSUFFICIENT_VALID_FOLDS",
                        "Fewer than four train-selected out-of-sample folds",
                        valid_folds=len(fold_records), bars=len(f))
    x, y = np.array(oos, dtype=float), np.array(benchmark, dtype=float)
    equity, passive = float(np.prod(1 + x) - 1), float(np.prod(1 + y) - 1)
    ci = _block_ci(x - y)
    # Even a positive backtest is NOT a verified executable edge or entry approval.
    return {
        "symbol": symbol, "model_version": VERSION, "status": "EVALUATED_RESEARCH_ONLY",
        "decision": "RESEARCH_ONLY", "trade_authorized": False,
        "observed_at": str(f["date"].iloc[-1].date()), "retrieved_at": retrieved.isoformat(),
        "source": meta["source"], "bars": len(f), "oos_days": len(x),
        "fee_bps_one_way": float(fee_bps),
        "strategies_pre_registered": list(STRATEGIES),
        "train_sessions": TRAIN, "test_sessions": TEST, "embargo_sessions": EMBARGO,
        "folds": fold_records, "oos_return_net": equity,
        "buy_hold_return_net": passive, "oos_excess_return": equity - passive,
        "oos_sharpe": _sharpe(x), "oos_max_drawdown": _max_drawdown(x),
        "annualized_alpha_arithmetic_ci95_block": ci,
        "confidence": "UNVERIFIED_STATISTICAL_EDGE",
        "limitations": [
            "Historical adjusted prices may contain ex-post corporate-action revisions",
            "Yahoo chart snapshots are not independently verified point-in-time histories",
            "Two candidate rules and many symbols imply selection/multiple-testing risk",
            "Bootstrap ignores some market dependence and does not certify significance",
            "Broker costs, fills, spread, FX and survivorship are not independently verified",
            "No future-looking trading signal or position recommendation is produced",
        ],
        "research_fingerprint": hashlib.sha256(
            (VERSION + "|" + symbol + "|" + str(f["date"].iloc[-1].date())
             + "|" + str(len(f)) + "|" + str(fee_bps) + "|"
             + hashlib.sha256(adjusted_close.to_numpy(dtype='float64').tobytes()).hexdigest()).encode()).hexdigest()[:16],
    }


def evaluate_cached(root, symbols, *, as_of=None, fee_bps=10.0):
    """Read existing, immutable local market snapshots. NEVER calls any provider."""
    stamp = _utc(as_of or datetime.now(timezone.utc))
    if stamp is None:
        raise ValueError("timezone-aware as_of required")
    root = Path(root)
    snapshots = Store(root).latest_snapshots(as_of=stamp.isoformat())
    results = []
    for symbol in list(dict.fromkeys(symbols)):
        record = snapshots.get(symbol)
        if not record:
            results.append(_abstain(symbol, "NO_SNAPSHOT", "Refresh the existing market cache first"))
            continue
        bars, meta = normalize(record, symbol, as_of=stamp.isoformat())
        results.append(evaluate_history(symbol, bars, meta, as_of=stamp, fee_bps=fee_bps))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": stamp.isoformat(), "model_version": VERSION,
        "purpose": "Quantitative research audit, never automatic trading",
        "results": results,
        "portfolio_data_included": False,
    }


def write_report(report, output):
    """JSON export outside versioned research sources; no broker or credential data."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return output
