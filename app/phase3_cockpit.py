"""Phase 3 decision cockpit layered onto the existing Streamlit research terminal.

No brokerage access or account data are loaded here. All unverified execution
conditions fail closed in the Committee policy.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.intelligence.phase3_committee import ranked_decisions, evaluate

ENGINE_VIEWS = {
    "Investment Committee": None,
    "Druckenmiller · Macro": "Druckenmiller",
    "Livermore · Execution": "Livermore",
    "Burry · Mispricing": "Burry",
    "Buffett · Quality": "Buffett",
}


def _candidates(data, filtered, horizon):
    opportunities = (data.get("opportunities") or {}).get(horizon)
    if not isinstance(opportunities, pd.DataFrame) or opportunities.empty:
        return pd.DataFrame()
    frame = opportunities[opportunities.symbol.isin(set(filtered.get("symbol", [])))].copy()
    return frame[frame.get("rank", pd.Series(index=frame.index, dtype=float)).notna()]


def _portfolio_note():
    st.caption(
        "Portfolio impact: DATA UNAVAILABLE in the public Committee. "
        "Fineco and eToro remain separate, session-private workflows; "
        "an account snapshot is not inferred from prices, and no orders are sent."
    )


def _engine_summary(item, key):
    state = item["state"]
    st.markdown(f"**{key}: {state}** — {item['thesis']}")
    for fact in item.get("evidence", ()):
        st.caption("Evidence: " + str(fact))
    if item.get("missing"):
        st.caption("Missing: " + "; ".join(item["missing"]))
    st.caption("Confidence: " + item["confidence"])


def _decision_card(item, idx):
    with st.container(border=True):
        ticker = item.get("symbol") or "UNKNOWN"
        st.markdown(f"**{idx}. {ticker} — {item['action']}**")
        st.caption(f"{item.get('name') or 'Name unavailable'} · horizon {item.get('horizon') or 'unknown'}")
        st.write(f"Attractiveness: technical within-class rank {item.get('technical_rank') or '—'}; "
                 f"readiness: {item['readiness']}. Not a forecast of returns.")
        tech = item["engines"]["Livermore"]
        st.write(tech["thesis"])
        if item.get("price") is not None:
            st.caption(f"Observed price {item['price']:.2f} (provider quote currency).")
        if item.get("entry_threshold") is not None:
            st.caption(f"Prior-20-session resistance {item['entry_threshold']:.2f}: "
                       "research confirmation only, NOT an approved entry.")
        if item.get("invalidation") is not None:
            st.caption(f"Prior-20-session support {item['invalidation']:.2f}: "
                       "structure invalidation, NOT a broker stop.")
        st.caption(f"Position sizing: {'DATA UNAVAILABLE' if item['position_size'] is None else str(item['position_size'])}. "
                   f"Risk Officer: {item['risk']['state']}. Confidence: {item['confidence']}.")
        st.caption("Source: " + str(item.get("source") or "MISSING") + " · Observed: "
                   + str(item.get("observed_at") or "MISSING") + " · Acquired: "
                   + str(item.get("retrieved_at") or "MISSING"))
        with st.expander("Four engines, risk gates and portfolio effects"):
            for key, value in item["engines"].items():
                _engine_summary(value, key)
            for blocker in item["risk"]["blockers"]:
                st.caption("RISK BLOCK: " + blocker)
            st.write("Portfolio: " + item["portfolio_impact"])
            st.caption(item["policy"])


def render_cockpit(data, filtered, horizon):
    """Overview first: max 3 researched decisions, no unqualified BUY flags."""
    candidates = _candidates(data, filtered, horizon)
    selections = ranked_decisions(candidates, data.get("macro"), limit=3)
    macro = data.get("macro") or {}
    st.markdown("### PHASE 3 — INVESTMENT DECISION COCKPIT")
    st.caption(f"Regime: {macro.get('label') or 'DATA UNAVAILABLE'} · macro evidence: "
               f"{macro.get('status') or 'MISSING'} · no synthetic probabilities")
    comparable = candidates.get("rank_change", pd.Series(dtype=float)).dropna()
    if comparable.empty:
        st.caption("What changed: DATA UNAVAILABLE — no comparable previous ranking/model coverage.")
    else:
        st.caption(f"What changed: {len(comparable)} comparable rank observations. "
                   "See individual rank deltas below; no inference about market cause.")
    if not selections:
        st.warning("NO TRADE — no qualified shortlisted instruments. Check acquisition and data-quality gates.")
    else:
        columns = st.columns(min(3, len(selections)))
        for i, (column, decision) in enumerate(zip(columns, selections), start=1):
            with column:
                _decision_card(decision, i)
    st.caption("Acting now vs waiting: entries are blocked until independently validated "
               "strategy, market data, risk, broker suitability and portfolio checks pass. "
               "The ranking is attractiveness research, not entry readiness.")
    _portfolio_note()


def render_engine_view(view, data, filtered, horizon):
    """Persistent research-terminal views, deliberately not a second standalone app."""
    st.markdown(f"### {view}")
    candidates = _candidates(data, filtered, horizon)
    items = ranked_decisions(candidates, data.get("macro"), limit=10)
    if not items:
        st.warning("DATA UNAVAILABLE — no qualified instruments in the selected scope.")
        return
    engine_key = ENGINE_VIEWS.get(view)
    if engine_key == "Druckenmiller":
        macro = data.get("macro") or {}
        st.write(macro.get("reason") or "Macro observations unavailable.")
        st.caption("Historical release vintages unavailable; not a point-in-time macro backtest.")
    st.caption("Every assessment lists evidence, missing inputs and confidence. "
               "ABSTAIN is not a neutral score; research is not a portfolio order.")
    for decision in items:
        label = f"{decision.get('symbol') or 'UNKNOWN'} · {decision['action']} · {decision['readiness']}"
        with st.expander(label):
            if engine_key:
                _engine_summary(decision["engines"][engine_key], engine_key)
            else:
                for engine, result in decision["engines"].items():
                    _engine_summary(result, engine)
                st.write("Committee: " + decision["action"])
                st.write("Risk Officer: " + decision["risk"]["state"])
                for blocker in decision["risk"]["blockers"]:
                    st.caption("RISK BLOCK: " + blocker)
                st.caption("Portfolio: " + decision["portfolio_impact"])
                st.caption("Model: " + decision["model_version"] + " · ID " + decision["id"])
    _portfolio_note()
