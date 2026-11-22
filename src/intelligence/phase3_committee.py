"""Phase 3 deterministic Investment Committee. Research only; never execute orders.

Inputs must be existing qualified snapshots. Missing information is not scored as
neutral and technical rank is never interpreted as expected return.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math

MODEL_VERSION = "phase3-committee-v1"
CORPORATE_KINDS = {"EQUITY", "STOCK"}


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def instant(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def dcf_per_share(owner_earnings, shares, net_debt, growth, discount_rate,
                  terminal_growth, years=10):
    """Finite-horizon owner-earnings DCF; explicit assumptions, no market data fetch."""
    values = [finite(v) for v in (owner_earnings, shares, net_debt, growth, discount_rate, terminal_growth)]
    if any(v is None for v in values) or not isinstance(years, int) or isinstance(years, bool):
        return None
    earnings, shares, debt, g, r, tg = values
    if (earnings <= 0 or shares <= 0 or years not in range(1, 21)
            or not -0.5 <= g <= 0.3 or not 0 < r <= 0.35
            or not -0.05 <= tg < r or r - tg < 0.015):
        return None
    flows = [earnings * (1 + g) ** year / (1 + r) ** year
             for year in range(1, years + 1)]
    terminal = earnings * (1 + g) ** years * (1 + tg) / (r - tg)
    equity = sum(flows) + terminal / (1 + r) ** years - debt
    return equity / shares if math.isfinite(equity) else None


def assessment(engine, state, thesis, evidence=(), missing=(), confidence="UNAVAILABLE"):
    return {"engine": engine, "state": state, "thesis": thesis,
            "evidence": list(evidence), "missing": list(missing),
            "confidence": confidence}


def macro_engine(macro):
    macro = macro if isinstance(macro, dict) else {}
    label = str(macro.get("label") or "DATA UNAVAILABLE")
    # Current FRED snapshot uses revised series; its historical publication
    # vintages cannot support an independently validated entry decision.
    if macro.get("status") != "VALID":
        return assessment("Druckenmiller", "ABSTAIN",
                          "Macro regime is contextual, not an entry signal.",
                          [label] if macro.get("status") == "DEGRADED" else [],
                          ["Qualified point-in-time macro vintages", "Cross-asset policy/credit confirmation"])
    return assessment("Druckenmiller", "WATCH", label,
                      [str(macro.get("reason") or label)], confidence="CONTEXT_ONLY")


def livermore_engine(row):
    if row.get("price_status") != "VALID" or row.get("signal_state") == "BLOCKED":
        return assessment("Livermore", "ABSTAIN", "Price/technical structure not qualified.",
                          missing=["Valid price and non-blocked ranking"])
    price, m50, m200 = (finite(row.get(k)) for k in ("price", "sma50", "sma200"))
    resistance, support = (finite(row.get(k)) for k in ("resistance20", "support20"))
    if any(x is None or x <= 0 for x in (price, m50, m200, resistance, support)):
        return assessment("Livermore", "ABSTAIN", "Cannot validate technical setup.",
                          missing=["Price, SMA50, SMA200, prior-20-session support/resistance"])
    breakout = price > resistance
    constructive = price > m50 > m200
    state = "CONSTRUCTIVE" if constructive and breakout else "CAUTION" if price < m50 and price < m200 else "WATCH"
    evidence = [f"Price {price:.2f}; SMA50 {m50:.2f}; SMA200 {m200:.2f}",
                f"Prior 20-session resistance {resistance:.2f}, support {support:.2f}",
                f"Breakout confirmed: {breakout}"]
    if row.get("volume_status") == "VALID" and finite(row.get("rvol_20")) is not None:
        evidence.append(f"Relative volume 20: {finite(row['rvol_20']):.2f}x")
    return assessment("Livermore", state,
                      "Bullish price structure; entry remains unvalidated." if state == "CONSTRUCTIVE"
                      else "Technical setup needs confirmation." if state == "WATCH"
                      else "Weak structure, avoid a momentum entry.",
                      evidence, ["Validated execution/stop model", "Broker-aware position sizing"],
                      confidence="DESCRIPTIVE_ONLY")


def _corporate_fundamentals(row, now):
    if str(row.get("kind", "")).upper() not in CORPORATE_KINDS:
        return None, "NOT_APPLICABLE"
    f = row.get("fundamentals")
    if not isinstance(f, dict) or not f.get("source") or not f.get("verified"):
        return None, "No verified corporate financial statements"
    timestamp = instant(f.get("as_of"))
    if not timestamp or not 0 <= (now - timestamp).total_seconds() <= 120 * 86400:
        return None, "Stale or unavailable fundamental observation"
    return f, None


def burry_engine(row, now):
    f, issue = _corporate_fundamentals(row, now)
    if f is None:
        return assessment("Burry", "ABSTAIN",
                          "Corporate mispricing is not inferred from ETF price momentum.",
                          missing=[issue] if issue != "NOT_APPLICABLE" else [],
                          confidence="NOT_APPLICABLE" if issue == "NOT_APPLICABLE" else "UNAVAILABLE")
    required = ("normalized_eps", "peer_pe", "net_debt_ebitda", "interest_coverage")
    x = {k: finite(f.get(k)) for k in required}
    price = finite(row.get("price"))
    if not price or price <= 0 or any(v is None for v in x.values()):
        return assessment("Burry", "ABSTAIN", "Cannot estimate normalized relative valuation.",
                          missing=[k for k, v in x.items() if v is None] + ([] if price else ["price"]))
    if x["normalized_eps"] <= 0 or x["peer_pe"] <= 0 or x["net_debt_ebitda"] < 0:
        return assessment("Burry", "ABSTAIN", "Invalid valuation/fragility assumptions.")
    fair = x["normalized_eps"] * x["peer_pe"]
    mos = 1 - price / fair
    fragile = x["net_debt_ebitda"] > 3 or x["interest_coverage"] < 2
    state = "CAUTION" if fragile else "CONSTRUCTIVE" if mos >= .25 else "WATCH"
    return assessment("Burry", state, "Normalized P/E scenario, not a certified fair value.",
                      [f"Relative fair-price scenario {fair:.2f}", f"Margin of safety {mos:.1%}",
                       f"Net debt/EBITDA {x['net_debt_ebitda']:.2f}; interest coverage {x['interest_coverage']:.2f}"],
                      ["Earnings quality and revisions", "Refinancing calendar", "Scenario sensitivity"],
                      confidence="MODEL_ESTIMATE")


def buffett_engine(row, now):
    f, issue = _corporate_fundamentals(row, now)
    if f is None:
        return assessment("Buffett", "ABSTAIN",
                          "Business intrinsic value is not applicable to generic ETF/bond/FX proxies.",
                          missing=[issue] if issue != "NOT_APPLICABLE" else [],
                          confidence="NOT_APPLICABLE" if issue == "NOT_APPLICABLE" else "UNAVAILABLE")
    keys = ("owner_earnings", "shares", "net_debt", "growth", "discount_rate", "terminal_growth")
    if any(finite(f.get(k)) is None for k in keys):
        return assessment("Buffett", "ABSTAIN", "Auditable owner-earnings inputs missing.",
                          missing=[k for k in keys if finite(f.get(k)) is None])
    fair = dcf_per_share(*(f[k] for k in keys))
    price = finite(row.get("price"))
    if fair is None or fair <= 0 or price is None or price <= 0:
        return assessment("Buffett", "ABSTAIN", "DCF assumptions invalid or price unqualified.")
    low = dcf_per_share(f["owner_earnings"], f["shares"], f["net_debt"],
                        f["growth"], f["discount_rate"] + .02, f["terminal_growth"])
    high = dcf_per_share(f["owner_earnings"], f["shares"], f["net_debt"],
                         f["growth"], max(.02, f["discount_rate"] - .02), f["terminal_growth"])
    mos = 1 - price / fair
    return assessment("Buffett", "CONSTRUCTIVE" if mos >= .25 else "WATCH",
                      "Assumption-dependent owner-earnings DCF; business moat not yet verified.",
                      [f"DCF base {fair:.2f} per share",
                       f"Sensitivity (+/- 2pp discount): {low:.2f} to {high:.2f}" if low is not None and high is not None else "Sensitivity unavailable",
                       f"Margin of safety {mos:.1%}"],
                      ["Independent moat/capital allocation review", "Audited cash-flow normalization"],
                      confidence="MODEL_ESTIMATE")


def risk_officer(row, now, portfolio=None):
    """Fail closed for transactions; research/watch may remain visible."""
    blockers, warnings = [], []
    if row.get("price_status") != "VALID" or row.get("signal_state") == "BLOCKED":
        blockers.append("Price quality/ranking gate failed")
    retrieved = instant(row.get("retrieved_at") or row.get("updated_at"))
    observation = row.get("observed_at")
    observed = instant(observation)
    if observed is None and isinstance(observation, str) and len(observation) == 10:
        observed = instant(observation + "T00:00:00+00:00")
    if not retrieved or not 0 <= (now - retrieved).total_seconds() <= 96 * 3600:
        blockers.append("Missing/stale provider acquisition timestamp")
    if not observed or not 0 <= (now - observed).total_seconds() <= 6 * 86400:
        blockers.append("Missing/stale market observation")
    if str(row.get("kind", "")).upper() not in {"ETF", "ETP", "FX", "EQUITY", "STOCK"}:
        blockers.append("Instrument is not an eligible tradable security")
    if row.get("entry_validation") != "VALIDATED":
        blockers.append("Entry/stop strategy not independently validated")
    if portfolio is None or not isinstance(portfolio, dict) or not portfolio.get("verified"):
        blockers.append("Verified portfolio and buying-power snapshot unavailable")
    else:
        snapshot_at = instant(portfolio.get("as_of"))
        if snapshot_at is None or not 0 <= (now - snapshot_at).total_seconds() <= 72 * 3600:
            blockers.append("Verified portfolio timestamp missing/stale")
        if portfolio.get("broker_available") is not True:
            blockers.append("Broker eligibility not verified")
        if portfolio.get("instrument_type") not in {"UNDERLYING", "UCITS_ETF", "PHYSICAL_ETC"}:
            blockers.append("Instrument type not verified as unleveraged underlying (CFD risk)")
        lev = finite(portfolio.get("leverage"))
        if lev is None or lev > 1 or lev < 0:
            blockers.append("Leverage absent or above unlevered limit")
        w = finite(portfolio.get("post_trade_weight"))
        if w is None or not 0 <= w <= .10:
            blockers.append("Post-trade single-instrument concentration absent/excessive")
        if portfolio.get("correlation_checked") is not True:
            blockers.append("Cross-portfolio correlation gate unavailable")
        if portfolio.get("fx_checked") is not True:
            blockers.append("Currency-risk gate unavailable")
        if portfolio.get("liquidity_checked") is not True:
            blockers.append("Instrument liquidity gate unavailable")
        if portfolio.get("drawdown_budget_ok") is not True:
            blockers.append("Aggregate drawdown budget not verified")
    if row.get("volume_status") != "VALID":
        warnings.append("Volume is not independently qualified")
    return {"state": "BLOCK" if blockers else "PASS", "blockers": blockers, "warnings": warnings,
            "max_position_weight": None if blockers else .10}


def evaluate(row, macro=None, portfolio=None, now=None):
    """Deterministic action policy: attractiveness is separate from trade readiness."""
    now = instant(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Evaluation time must be timezone aware")
    row = dict(row)
    engines = {
        "Druckenmiller": macro_engine(macro),
        "Livermore": livermore_engine(row),
        "Burry": burry_engine(row, now),
        "Buffett": buffett_engine(row, now),
    }
    risk = risk_officer(row, now, portfolio)
    technical = engines["Livermore"]["state"]
    applicable = [v for v in engines.values() if v["confidence"] != "NOT_APPLICABLE"]
    positives = sum(v["state"] == "CONSTRUCTIVE" for v in applicable)
    # No opaque weighted average. Explicit veto and quorum.
    if row.get("price_status") != "VALID" or technical == "ABSTAIN":
        action, readiness = "NO TRADE", "DATA UNAVAILABLE"
    elif technical == "CAUTION":
        action, readiness = "AVOID", "TECHNICAL CAUTION"
    elif risk["state"] == "PASS" and positives >= 2 and technical == "CONSTRUCTIVE":
        action, readiness = "BUY NOW", "RISK CLEARED"
    else:
        action, readiness = "WAIT", "RESEARCH ONLY"
    source_id = "|".join(str(row.get(k) or "") for k in ("symbol", "observed_at", "retrieved_at", "horizon"))
    decision_id = hashlib.sha256((MODEL_VERSION + "|" + source_id).encode()).hexdigest()[:16]
    return {
        "id": decision_id, "model_version": MODEL_VERSION, "symbol": row.get("symbol"),
        "name": row.get("name"), "asset_class": row.get("asset_class"),
        "horizon": row.get("horizon"), "action": action, "readiness": readiness,
        "attractiveness": row.get("opportunity_score") if row.get("signal_state") != "BLOCKED" else None,
        "technical_rank": row.get("rank"), "price": finite(row.get("price")),
        "entry_threshold": finite(row.get("resistance20")) if technical != "ABSTAIN" else None,
        "invalidation": finite(row.get("support20")) if technical != "ABSTAIN" else None,
        "position_size": None if risk["state"] == "BLOCK" else risk["max_position_weight"],
        "portfolio_impact": "DATA UNAVAILABLE" if portfolio is None else "Requires portfolio scenario validation",
        "risk": risk, "engines": engines,
        "confidence": "RESEARCH ONLY" if risk["state"] == "BLOCK" else "CONDITIONAL",
        "source": row.get("source"), "observed_at": row.get("observed_at"),
        "retrieved_at": row.get("retrieved_at"),
        "policy": "Blocked data -> NO TRADE; weak structure -> AVOID; validated entry + 2 constructive engines + all risk gates -> BUY NOW; otherwise WAIT.",
    }


def ranked_decisions(frame, macro=None, portfolio=None, now=None, limit=10):
    """Preserves upstream global rank; filtering never re-ranks the universe."""
    if frame is None or frame.empty:
        return []
    order = frame.sort_values(["rank", "symbol"], na_position="last")
    return [evaluate(row, macro, portfolio, now) for row in order.head(limit).to_dict("records")]
