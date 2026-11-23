"""Tests use clearly synthetic, deterministic fixtures only, never live signals."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.intelligence.simons_quant import evaluate_history, evaluate_cached, VERSION


def fixture(rows=720):
    d = pd.bdate_range(end="2026-11-20", periods=rows)
    t = np.arange(rows, dtype=float)
    close = 100 * np.exp(0.0005 * t + 0.025 * np.sin(t / 16))
    daily_open = close * (1 + 0.002 * np.sin(t / 5))
    f = pd.DataFrame({
        "date": d, "open": daily_open,
        "close": close,
        "adj_close": close,
        "high": np.maximum(daily_open, close) * 1.005,
        "low": np.minimum(daily_open, close) * 0.995,
        "volume": np.full(rows, 1_000_000),
    })
    meta = {"source": "Yahoo Finance", "price_status": "VALID",
            "retrieved_at": "2026-11-21T12:00:00+00:00"}
    return f, meta


AS_OF = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


def test_four_out_of_sample_folds_and_no_trade_authority():
    f, m = fixture()
    result = evaluate_history("TEST-FIXTURE", f, m, as_of=AS_OF)
    assert result["status"] == "EVALUATED_RESEARCH_ONLY"
    assert len(result["folds"]) >= 4
    assert result["oos_days"] >= 4 * 42
    assert result["trade_authorized"] is False
    assert result["decision"] == "RESEARCH_ONLY"
    assert set(x["selected_on_training"] for x in result["folds"]) <= set(result["strategies_pre_registered"])
    assert result["oos_sharpe"] is not None
    assert result["model_version"] == VERSION


def test_later_price_change_does_not_rewrite_earlier_folds():
    f, m = fixture()
    baseline = evaluate_history("FIXTURE", f, m, as_of=AS_OF)
    altered = f.copy()
    altered.loc[len(altered) - 2:, ["close", "adj_close", "open"]] *= 1.15
    altered["high"] = altered[["open", "close"]].max(axis=1) * 1.005
    altered["low"] = altered[["open", "close"]].min(axis=1) * .995
    other = evaluate_history("FIXTURE", altered, m, as_of=AS_OF)
    assert baseline["folds"][:2] == other["folds"][:2]


def test_costs_never_improve_a_given_backtest_when_strategy_choice_is_stable():
    f, m = fixture()
    zero = evaluate_history("FIXTURE", f, m, as_of=AS_OF, fee_bps=0)
    paid = evaluate_history("FIXTURE", f, m, as_of=AS_OF, fee_bps=10)
    assert zero["status"] == paid["status"] == "EVALUATED_RESEARCH_ONLY"
    assert zero["buy_hold_return_net"] >= paid["buy_hold_return_net"]


def test_fail_closed_without_verified_market_provenance():
    f, m = fixture()
    assert evaluate_history("X", f, {**m, "price_status": "SYNTHETIC"}, as_of=AS_OF)["decision"] == "ABSTAIN"
    assert evaluate_history("X", f, {**m, "source": "unknown"}, as_of=AS_OF)["status"] == "UNQUALIFIED_SOURCE"
    assert evaluate_history("X", f, {**m, "retrieved_at": "2026-11-24T00:00:00Z"}, as_of=AS_OF)["decision"] == "ABSTAIN"
    assert evaluate_history("X", f, {**m, "retrieved_at": "2026-01-01T00:00:00Z"}, as_of=AS_OF)["decision"] == "ABSTAIN"


def test_insufficient_history_and_broken_bars_are_rejected():
    f, m = fixture(rows=420)
    assert evaluate_history("X", f, m, as_of=AS_OF)["status"] == "INSUFFICIENT_HISTORY"
    f2, m2 = fixture()
    f2.loc[0, "open"] = -2
    assert evaluate_history("X", f2, m2, as_of=AS_OF)["status"] == "INVALID_BARS"


def test_as_of_requires_timezone_and_excludes_future_bars():
    f, m = fixture()
    assert evaluate_history("X", f, m, as_of="2026-11-23T10:00:00")["status"] == "INVALID_INPUT"
    f.loc[len(f) - 1, "date"] = pd.Timestamp("2026-11-23")
    assert evaluate_history("X", f, m, as_of=AS_OF)["status"] == "FUTURE_BAR"


def test_missing_local_cache_never_creates_fake_results(tmp_path):
    report = evaluate_cached(tmp_path, ["SPY"], as_of=AS_OF)
    assert report["results"][0]["status"] == "NO_SNAPSHOT"
    assert report["portfolio_data_included"] is False
