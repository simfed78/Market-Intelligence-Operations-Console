"""Synthetic fixtures: no production price, invented position or broker signal."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.intelligence.phase3_committee import (
    dcf_per_share, evaluate, macro_engine, risk_officer, ranked_decisions,
)

NOW = datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc)


def asset(**overrides):
    row = {
        "symbol": "SAMPLE", "name": "Synthetic ETF fixture", "asset_class": "Azioni",
        "kind": "ETF", "price_status": "VALID", "volume_status": "VALID",
        "signal_state": "RESEARCH CANDIDATE", "price": 120.,
        "sma50": 110., "sma200": 100., "resistance20": 118.,
        "support20": 104., "rvol_20": 1.3, "rank": 2, "horizon": "3m",
        "opportunity_score": 85., "entry_validation": "MISSING",
        "observed_at": "2026-11-20",
        "retrieved_at": "2026-11-21T20:00:00+00:00", "source": "Fixture provider",
    }
    row.update(overrides)
    return row


def approved_portfolio(**changes):
    result = {"verified": True, "broker_available": True,
              "as_of": "2026-11-22T18:00:00Z", "drawdown_budget_ok": True,
              "instrument_type": "UNDERLYING", "leverage": 1,
              "post_trade_weight": .08, "correlation_checked": True,
              "fx_checked": True, "liquidity_checked": True}
    result.update(changes)
    return result


def test_research_candidates_are_not_automatic_buys():
    x = evaluate(asset(), {"status": "DEGRADED", "label": "expansion"}, now=NOW)
    assert x["action"] == "WAIT" and x["readiness"] == "RESEARCH ONLY"
    assert x["risk"]["state"] == "BLOCK"
    assert x["position_size"] is None and x["portfolio_impact"] == "DATA UNAVAILABLE"
    assert x["engines"]["Livermore"]["state"] == "CONSTRUCTIVE"
    assert x["engines"]["Druckenmiller"]["state"] == "ABSTAIN"
    assert x["engines"]["Burry"]["confidence"] == "NOT_APPLICABLE"
    assert x["engines"]["Buffett"]["confidence"] == "NOT_APPLICABLE"
    assert x["entry_threshold"] == 118. and x["invalidation"] == 104.


@pytest.mark.parametrize("problem", [
    {"price_status": "SYNTHETIC"},
    {"price_status": "DEGRADED"},
    {"retrieved_at": "2026-10-01T00:00:00Z"},
    {"retrieved_at": None},
    {"observed_at": "2026-10-01"},
])
def test_unqualified_market_data_never_clears_risk(problem):
    x = evaluate(asset(**problem), now=NOW)
    assert x["risk"]["state"] == "BLOCK"
    assert x["action"] != "BUY NOW"


def test_no_buy_without_entry_validation_even_if_broker_and_technical_look_good():
    x = evaluate(asset(), {"status": "VALID", "label": "macro qualified"},
                 approved_portfolio(), NOW)
    assert x["action"] == "WAIT"
    assert "Entry/stop strategy" in " ".join(x["risk"]["blockers"])


def test_action_reaches_buy_only_with_independent_quorum_and_all_risk_checks():
    valid = asset(entry_validation="VALIDATED")
    macro = {"status": "VALID", "label": "qualified macro context"}
    # Macro is contextual WATCH, not constructive; one technical engine cannot
    # constitute a two-engine investment committee approval.
    x = evaluate(valid, macro, approved_portfolio(), NOW)
    assert x["risk"]["state"] == "PASS"
    assert x["action"] == "WAIT"


def test_cfd_and_concentration_are_hard_blocks():
    row = asset(entry_validation="VALIDATED")
    x = risk_officer(row, NOW, approved_portfolio(instrument_type="CFD", post_trade_weight=.25))
    assert x["state"] == "BLOCK"
    assert any("CFD" in blocker for blocker in x["blockers"])
    assert any("concentration" in blocker for blocker in x["blockers"])


def test_missing_strategy_price_structure_abstains():
    x = evaluate(asset(sma50=None, support20=None), now=NOW)
    assert x["engines"]["Livermore"]["state"] == "ABSTAIN"
    assert x["action"] == "NO TRADE"


def test_dcf_is_real_math_with_explicit_assumptions_and_sensitivity():
    result = dcf_per_share(100, 10, 0, 0, .10, 0, years=10)
    assert result == pytest.approx(100., rel=1e-10)
    assert dcf_per_share(100, 10, 0, .1, .03, .04) is None
    assert dcf_per_share(-100, 10, 0, 0, .10, 0) is None


def test_verified_corporate_data_produce_separate_estimators():
    f = {"source": "Certified fixture", "verified": True,
         "as_of": "2026-11-20T10:00:00Z", "normalized_eps": 10,
         "peer_pe": 15, "net_debt_ebitda": 1.5, "interest_coverage": 10,
         "owner_earnings": 100, "shares": 10, "net_debt": 0,
         "growth": 0, "discount_rate": .10, "terminal_growth": 0}
    x = evaluate(asset(kind="EQUITY", fundamentals=f), now=NOW)
    assert x["engines"]["Burry"]["state"] == "WATCH"
    assert x["engines"]["Buffett"]["state"] == "WATCH"
    assert x["action"] == "WAIT"


def test_rank_filter_preserves_order_and_limited_top_three():
    a, b, c = asset(symbol="A",rank=5),asset(symbol="B",rank=2),asset(symbol="C",rank=1)
    rows = ranked_decisions(pd.DataFrame([a,b,c]), now=NOW, limit=2)
    assert [x["symbol"] for x in rows] == ["C", "B"]
    assert all(x["risk"]["state"] == "BLOCK" for x in rows)


def test_naive_or_future_timestamps_fail_closed():
    assert risk_officer(asset(retrieved_at="2026-11-22T19:00:00"), NOW)["state"] == "BLOCK"
    future = (NOW + timedelta(days=2)).isoformat()
    assert risk_officer(asset(retrieved_at=future), NOW)["state"] == "BLOCK"
    assert macro_engine({"status":"DEGRADED","label":"historically revised"})["state"] == "ABSTAIN"


def test_stale_portfolio_or_missing_drawdown_budget_cannot_clear_risk():
    approved = asset(entry_validation="VALIDATED")
    stale = risk_officer(approved, NOW, approved_portfolio(as_of="2026-10-01T00:00:00Z"))
    assert stale["state"] == "BLOCK"
    assert any("portfolio timestamp" in value for value in stale["blockers"])
    unchecked = risk_officer(approved, NOW, approved_portfolio(drawdown_budget_ok=False))
    assert unchecked["state"] == "BLOCK"
    assert any("drawdown" in value for value in unchecked["blockers"])
