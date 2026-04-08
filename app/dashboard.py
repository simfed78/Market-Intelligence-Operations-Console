"""Streamlit operational dashboard entrypoint."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.dashboard_data import (
    frame_from_payload,
    load_alert_history,
    load_latest_baskets,
    load_payload as _load_payload,
    load_run_history,
    load_score_history_frame,
    load_transition_history,
    load_what_changed,
)
from src.data.loaders import load_config_bundle
from src.orchestrator.run_daily_cycle import DailyCycleRunner
from src.orchestrator.run_weekly_cycle import WeeklyCycleRunner

KPI_HELP = {
    "SPX Regime": "Sintesi del contesto per l'indice. Valori alti indicano un backdrop piu favorevole al rischio, valori bassi un contesto piu fragile o difensivo.",
    "Sector Opportunity": "Misura quanto il motore vede opportunita interessanti nel paniere dei settori broad, combinando trend, contesto macro, liquidita e conferme.",
    "Cyclical Opportunity": "Stima quanto i segmenti piu ciclici stanno migliorando in modo credibile. E utile per capire se il mercato sta iniziando a premiare la crescita sensibile al ciclo.",
    "Risk Flag": "Etichetta sintetica del contesto di rischio corrente, ad esempio risk_on, neutral o risk_off.",
    "Exposure": "Overlay discrezionale derivato dai segnali. Non e un consiglio operativo automatico, ma una vista strutturata sul livello di aggressivita o cautela.",
    "Basket Return": "Performance storica semplice del basket corrente sul campione disponibile, utile solo come riferimento di ricerca.",
    "Relative": "Extra-performance del basket rispetto al benchmark configurato, di solito SPY.",
    "Drawdown": "Peggior flessione storica osservata nel basket sul campione considerato.",
    "Turnover": "Stima grezza di rotazione del basket. Valori piu alti implicano piu cambiamenti nella composizione o nei pesi.",
}

SECTION_HELP = {
    "Overview": "Vista rapida del regime corrente, delle opportunita principali e dei basket candidati.",
    "What Changed": "Mostra cosa e cambiato rispetto al run precedente: transizioni di ranking, deterioramento proxy e variazioni di stato.",
    "Candidate Baskets": "Basket di ricerca costruiti dalle classifiche correnti con regole trasparenti e configurabili.",
    "Exposure Model": "Traduzione dei segnali in una stance discrezionale sul rischio: offensiva, neutrale o difensiva.",
    "Proxy Health": "Stato di salute dei proxy: qualita, stabilita, segnali di decay e rotture strutturali.",
    "Run History": "Storico dei run salvati in SQLite, utile per vedere l'evoluzione dei punteggi nel tempo.",
    "Alert Center": "Storico e stato corrente di alert e watchlist generati dal motore.",
    "Quick Exports": "Elenco degli export pronti per workflow esterni come note TradingView o report manuali.",
}


def _inject_responsive_styles() -> None:
    """Apply dashboard styles tuned for smaller screens."""
    st.markdown(
        """
        <style>
        .stApp [data-testid="stAppViewContainer"] {
          background: #fcfcf9;
        }

        .stApp h1, .stApp h2, .stApp h3 {
          letter-spacing: -0.02em;
        }

        .stApp [data-testid="stMetric"] {
          border: 1px solid #e4e7ec;
          border-radius: 14px;
          padding: 0.65rem 0.8rem;
          background: #ffffff;
        }

        .stApp [data-testid="stDataFrame"] {
          border-radius: 12px;
          overflow: hidden;
        }

        .stApp [data-testid="stSidebar"] {
          border-right: 1px solid #e4e7ec;
        }

        @media (max-width: 900px) {
          .stApp .block-container {
            padding-top: 1rem;
            padding-left: 0.85rem;
            padding-right: 0.85rem;
            padding-bottom: 2rem;
          }

          .stApp h1 {
            font-size: 2rem;
            line-height: 1.1;
          }

          .stApp h2 {
            font-size: 1.55rem;
          }

          .stApp h3 {
            font-size: 1.2rem;
          }

          .stApp p, .stApp li, .stApp label, .stApp [data-testid="stCaptionContainer"] {
            font-size: 0.95rem;
            line-height: 1.45;
          }

          .stApp [data-testid="stHorizontalBlock"] {
            gap: 0.7rem;
          }

          .stApp [data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
          }

          .stApp button[kind="secondary"],
          .stApp button[kind="primary"] {
            width: 100%;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_payload(project_root: Path, weekly: bool = False) -> dict:
    """Backwards-compatible payload loader for tests and external callers."""
    return _load_payload(project_root, weekly=weekly)


def _load_ticker_groups(project_root: Path) -> dict[str, list[str]]:
    """Load ticker groups from config."""
    path = project_root / "config" / "tickers.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _asset_category_map(project_root: Path) -> dict[str, str]:
    """Create a ticker-to-category map for dashboard use."""
    groups = _load_ticker_groups(project_root)
    mapping: dict[str, str] = {}
    label_map = {
        "core_index": "Equities",
        "sectors": "Sector ETFs",
        "cyclical_detail": "Cyclical ETFs",
        "rates_bonds_credit": "Bonds / Credit",
        "commodities_cross_asset": "Commodities / FX",
        "volatility_sentiment": "Volatility",
        "manual_series": "Manual / Derived",
    }
    for group_name, tickers in groups.items():
        for ticker in tickers or []:
            mapping[str(ticker)] = label_map.get(group_name, "Other")
    return mapping


def _with_asset_category(frame: pd.DataFrame, project_root: Path) -> pd.DataFrame:
    """Append asset category to a ranking frame."""
    if frame.empty or "ticker" not in frame.columns:
        return frame
    out = frame.copy()
    category_map = _asset_category_map(project_root)
    out["asset_category"] = out["ticker"].map(category_map).fillna("Other")
    return out


def _parse_proxy_deterioration(text: str) -> pd.DataFrame:
    """Parse compact proxy deterioration text into a table."""
    if not text:
        return pd.DataFrame(columns=["proxy", "previous", "current", "delta"])
    rows: list[dict[str, float | str]] = []
    for part in text.split(","):
        item = part.strip()
        if " " not in item or "->" not in item:
            continue
        proxy, values = item.split(" ", 1)
        previous, current = values.split("->", 1)
        try:
            prev_val = float(previous)
            curr_val = float(current)
        except ValueError:
            continue
        rows.append(
            {
                "proxy": proxy,
                "previous": prev_val,
                "current": curr_val,
                "delta": curr_val - prev_val,
            }
        )
    return pd.DataFrame(rows)


def _build_research_actions(opportunities: pd.DataFrame, validation: pd.DataFrame, unstable: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create research-oriented buy and sell candidate tables."""
    if opportunities.empty:
        empty = pd.DataFrame(columns=["ticker", "name", "asset_category", "action_score", "description"])
        return empty, empty

    base = opportunities.copy()
    if "ticker" not in base.columns:
        empty = pd.DataFrame(columns=["ticker", "name", "asset_category", "action_score", "description"])
        return empty, empty

    validation_summary = pd.DataFrame(columns=["ticker", "proxy_quality_score", "stability_score", "predictive_usefulness_score"])
    if not validation.empty and "proxy" in validation.columns:
        validation_summary = (
            validation.groupby("proxy", as_index=False)[["proxy_quality_score", "stability_score", "predictive_usefulness_score"]]
            .mean()
            .rename(columns={"proxy": "ticker"})
        )
    unstable_set = set(unstable["proxy"].astype(str).tolist()) if not unstable.empty and "proxy" in unstable.columns else set()

    merged = base.merge(validation_summary, on="ticker", how="left")
    for col in ["proxy_quality_score", "stability_score", "predictive_usefulness_score", "proxy_stability", "early_opportunity_score"]:
        if col not in merged.columns:
            merged[col] = 0.0
    merged[["proxy_quality_score", "stability_score", "predictive_usefulness_score", "proxy_stability", "early_opportunity_score"]] = (
        merged[["proxy_quality_score", "stability_score", "predictive_usefulness_score", "proxy_stability", "early_opportunity_score"]]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )
    merged["is_unstable_proxy"] = merged["ticker"].astype(str).isin(unstable_set)
    merged["buy_score"] = (
        merged["early_opportunity_score"] * 0.45
        + merged["proxy_stability"] * 0.20
        + merged["proxy_quality_score"] * 0.20
        + merged["predictive_usefulness_score"] * 0.15
        - merged["is_unstable_proxy"].astype(float) * 12.0
    )
    merged["sell_score"] = (
        (100 - merged["early_opportunity_score"]) * 0.45
        + (100 - merged["proxy_stability"]) * 0.20
        + (100 - merged["stability_score"]) * 0.20
        + merged["is_unstable_proxy"].astype(float) * 15.0
        + (100 - merged["proxy_quality_score"]) * 0.15
    )

    def describe_buy(row: pd.Series) -> str:
        return (
            f"{row.get('name', row.get('ticker', ''))} is a research buy candidate in {row.get('asset_category', 'Other')}. "
            f"It ranks as {row.get('opportunity_label', 'n/a')} with opportunity {row.get('early_opportunity_score', 0):.1f}, "
            f"proxy stability {row.get('proxy_stability', 0):.1f}, and validation quality {row.get('proxy_quality_score', 0):.1f}."
        )

    def describe_sell(row: pd.Series) -> str:
        instability = " Structural-break or decay warnings are active." if bool(row.get("is_unstable_proxy", False)) else ""
        return (
            f"{row.get('name', row.get('ticker', ''))} is a research sell/avoid candidate in {row.get('asset_category', 'Other')}. "
            f"Opportunity quality is {row.get('early_opportunity_score', 0):.1f} with proxy stability {row.get('proxy_stability', 0):.1f}."
            f"{instability}"
        )

    buy = merged.sort_values(["buy_score", "early_opportunity_score"], ascending=False).head(5).copy()
    sell = merged.sort_values(["sell_score", "early_opportunity_score"], ascending=[False, True]).head(5).copy()
    buy["action_score"] = buy["buy_score"]
    sell["action_score"] = sell["sell_score"]
    buy["description"] = buy.apply(describe_buy, axis=1)
    sell["description"] = sell.apply(describe_sell, axis=1)
    cols = ["ticker", "name", "asset_category", "action_score", "description", "opportunity_label", "early_opportunity_score", "proxy_stability"]
    return buy[cols], sell[cols]


def _render_action_cards(title: str, frame: pd.DataFrame, color: str) -> None:
    """Render compact action cards."""
    st.markdown(f"#### {title}")
    if frame.empty:
        st.info(f"No {title.lower()} candidates available.")
        return
    for _, row in frame.iterrows():
        st.markdown(
            f"""
            <div style="border-left:6px solid {color}; padding:12px 14px; border-radius:8px; background:#ffffff; margin:0 0 10px 0; border:1px solid #e4e7ec;">
              <div style="font-size:16px; font-weight:700; color:#101828;">{row.get('ticker', '')} — {row.get('name', row.get('ticker', ''))}</div>
              <div style="font-size:12px; color:#475467; margin:4px 0 8px 0;">{row.get('asset_category', 'Other')} | Action score {row.get('action_score', 0):.1f}</div>
              <div style="font-size:13px; color:#344054;">{row.get('description', '')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _section_header(title: str, help_text: str | None = None) -> None:
    cols = st.columns([0.88, 0.12])
    cols[0].subheader(title)
    if help_text:
        with cols[1].popover("Info", help="Apri una spiegazione rapida di questa sezione"):
            st.write(help_text)


def _mode_badge(run_type: str, timestamp: str) -> None:
    """Render a colored payload mode badge."""
    is_weekly = run_type == "weekly"
    label = "WEEKLY" if is_weekly else "DAILY"
    bg = "#1d4ed8" if is_weekly else "#1f7a3d"
    source = "weekly_payload.json" if is_weekly else "daily_payload.json"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin:0 0 14px 0;">
          <span style="display:inline-block;padding:6px 10px;border-radius:999px;background:{bg};color:white;font-size:12px;font-weight:700;letter-spacing:0.04em;">
            {label}
          </span>
          <span style="font-size:13px;color:#475467;">
            Source: <strong>{source}</strong> | Timestamp: <strong>{timestamp or 'n/a'}</strong>
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _refresh_controls(project_root: Path) -> None:
    """Render a single dashboard-wide refresh action."""
    cols = st.columns([0.22, 0.78])
    button_label = "Refresh all dashboard data"
    help_text = "Rebuild both daily and weekly payloads so every dashboard tab reads from fresh data."
    if cols[0].button(button_label, help=help_text, use_container_width=True):
        with st.spinner("Refreshing all dashboard data..."):
            _refresh_all_payloads(project_root)
        st.success("Refresh completed.")
        st.rerun()
    cols[1].caption("This rebuilds both daily and weekly snapshots, so all tabs and payload views are refreshed together.")


def _semaphore_bucket(value: float, positive: float = 60.0, negative: float = 40.0) -> tuple[str, str]:
    """Map a score to a simple semaphore state."""
    if value >= positive:
        return "positive", "#1f7a3d"
    if value <= negative:
        return "negative", "#b42318"
    return "neutral", "#f59e0b"


def _risk_flag_semaphore(flag: str) -> tuple[str, str]:
    """Map risk flags to a semaphore state."""
    normalized = (flag or "").lower()
    if "risk_on" in normalized or normalized == "offensive":
        return "positive", "#1f7a3d"
    if "risk_off" in normalized or normalized in {"defensive", "capital preservation"}:
        return "negative", "#b42318"
    return "neutral", "#f59e0b"


def _label_to_meter_value(label: str) -> float:
    """Map stance labels to a gauge value."""
    normalized = (label or "").lower()
    if normalized in {"offensive", "risk_on"}:
        return 85.0
    if normalized == "moderately offensive":
        return 70.0
    if normalized in {"neutral", "unknown", "n/a"}:
        return 50.0
    if normalized in {"selective risk"}:
        return 40.0
    if normalized in {"defensive", "risk_off"}:
        return 25.0
    if normalized in {"capital preservation"}:
        return 10.0
    return 50.0


def _gauge_abstract(label: str, value: float, state: str) -> str:
    """Create a short explanatory abstract for each gauge."""
    if label == "SPX Regime":
        return f"Broad index backdrop is {state}, with a composite regime score of {value:.1f}."
    if label == "Sector Opportunity":
        return f"Sector rotation breadth is {state}, suggesting opportunity quality is {'improving' if state == 'positive' else 'mixed' if state == 'neutral' else 'thin'}."
    if label == "Cyclical Opportunity":
        return f"Cyclical leadership is {state}, which helps gauge how much the market is rewarding economic sensitivity."
    if label == "Macro":
        return f"Macro context is {state}, based on growth, inflation, labor, and policy proxies."
    if label == "Liquidity":
        return f"Liquidity and credit conditions read as {state}, a key filter for risk appetite."
    if label == "Sentiment":
        return f"Internals and sentiment are {state}, helping distinguish healthy participation from fragility."
    if label == "Risk Flag":
        return f"Current market risk posture is {state}, summarizing the engine's high-level environment tag."
    if label == "Exposure":
        return f"Suggested discretionary stance is {state}, translating signals into a practical risk posture."
    return f"Current state is {state} with a reading of {value:.1f}."


def _render_market_posture_banner(payload: dict) -> None:
    """Highlight risk flag and exposure with full readable text."""
    exposure = payload.get("exposure_view", {})
    risk_flag = str(payload.get("risk_environment_flag", "unknown"))
    exposure_label = str(exposure.get("exposure_stance_label", "n/a"))
    risk_state, risk_color = _risk_flag_semaphore(risk_flag)
    exposure_state, exposure_color = _risk_flag_semaphore(exposure_label)
    risk_summary = {
        "positive": "Risk appetite is supportive and the engine is not flagging broad defensive stress.",
        "neutral": "The market backdrop is mixed, so confirmation matters more than aggressive positioning.",
        "negative": "The engine sees a defensive or fragile backdrop, so caution and selectivity matter.",
    }
    exposure_summary = exposure.get(
        "exposure_summary",
        "Exposure view unavailable.",
    )
    cols = st.columns(2)
    cards = [
        (
            cols[0],
            "Risk Flag",
            risk_flag.replace("_", " "),
            risk_state,
            risk_color,
            risk_summary.get(risk_state, ""),
        ),
        (
            cols[1],
            "Exposure",
            exposure_label.replace("_", " "),
            exposure_state,
            exposure_color,
            exposure_summary,
        ),
    ]
    for col, title, value, state, color, summary in cards:
        col.markdown(
            f"""
            <div style="border:1px solid #d0d5dd;border-radius:14px;padding:16px 18px;background:#ffffff;min-height:154px;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
                <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};"></span>
                <span style="font-size:13px;font-weight:700;color:#475467;text-transform:uppercase;letter-spacing:0.04em;">{title}</span>
              </div>
              <div style="font-size:34px;line-height:1.1;font-weight:800;color:#101828;word-break:break-word;overflow-wrap:anywhere;margin-bottom:10px;">
                {value}
              </div>
              <div style="font-size:12px;font-weight:700;color:{color};text-transform:capitalize;margin-bottom:8px;">
                {state}
              </div>
              <div style="font-size:14px;line-height:1.45;color:#344054;word-break:break-word;overflow-wrap:anywhere;">
                {summary}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_gauge(container, label: str, value: float, color: str, state: str) -> None:
    """Render a compact speedometer-style gauge."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"font": {"size": 24}, "suffix": ""},
            title={"text": label, "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#98a2b3"},
                "bar": {"color": color, "thickness": 0.35},
                "bgcolor": "white",
                "borderwidth": 1,
                "bordercolor": "#d0d5dd",
                "steps": [
                    {"range": [0, 40], "color": "#fbeae9"},
                    {"range": [40, 60], "color": "#fff4cc"},
                    {"range": [60, 100], "color": "#e8f5ec"},
                ],
            },
        )
    )
    fig.update_layout(
        height=170,
        margin=dict(l=12, r=12, t=36, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#101828"},
    )
    container.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    container.caption(state.capitalize())
    container.caption(_gauge_abstract(label, value, state))


def _render_semaphore_row(payload: dict) -> None:
    """Render compact market gauges."""
    scores = payload.get("scores", {})
    exposure = payload.get("exposure_view", {})
    component_scores = payload.get("component_scores", {})
    items = [
        ("SPX Regime", float(scores.get("spx_regime_score", 0.0)), *_semaphore_bucket(float(scores.get("spx_regime_score", 0.0)), 60, 45)),
        ("Sector Opportunity", float(scores.get("sector_opportunity_score", 0.0)), *_semaphore_bucket(float(scores.get("sector_opportunity_score", 0.0)), 60, 45)),
        ("Cyclical Opportunity", float(scores.get("cyclical_opportunity_score", 0.0)), *_semaphore_bucket(float(scores.get("cyclical_opportunity_score", 0.0)), 55, 40)),
        ("Macro", float(component_scores.get("macro", 0.0)), *_semaphore_bucket(float(component_scores.get("macro", 0.0)), 60, 45)),
        ("Liquidity", float(component_scores.get("liquidity", 0.0)), *_semaphore_bucket(float(component_scores.get("liquidity", 0.0)), 60, 45)),
        ("Sentiment", float(component_scores.get("sentiment", 0.0)), *_semaphore_bucket(float(component_scores.get("sentiment", 0.0)), 60, 45)),
    ]
    risk_state, risk_color = _risk_flag_semaphore(str(payload.get("risk_environment_flag", "unknown")))
    exposure_state, exposure_color = _risk_flag_semaphore(str(exposure.get("exposure_stance_label", "neutral")))
    items.extend(
        [
            ("Risk Flag", _label_to_meter_value(str(payload.get("risk_environment_flag", "unknown"))), risk_state, risk_color),
            ("Exposure", _label_to_meter_value(str(exposure.get("exposure_stance_label", "n/a"))), exposure_state, exposure_color),
        ]
    )
    rows = [items[i : i + 2] for i in range(0, len(items), 2)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, raw_value, state, color) in zip(cols, row, strict=False):
            _render_gauge(col, label, float(raw_value), color, state)


def _agent_narrative(agent: str, summary: str) -> tuple[str, str]:
    """Translate agent output into a more narrative executive readout."""
    if agent == "macro_regime":
        return "Macro Backdrop", "Frames the broad economic regime and whether growth, inflation, and policy are helping or constraining risk-taking."
    if agent == "liquidity_rates_credit":
        return "Funding And Credit", "Shows whether rates pressure and credit conditions are acting as support or friction for the market."
    if agent == "cross_asset_leadlag":
        return "Cross-Asset Confirmation", "Highlights which proxies are actually leading SPX behavior right now and whether those relationships still look trustworthy."
    if agent == "sentiment_internals":
        return "Market Internals", "Measures how healthy the tape is under the surface, separating participation from fragility."
    if agent == "seasonality":
        return "Calendar Context", "Adds timing context from recurring patterns and event windows, without treating them as standalone triggers."
    if agent == "technical_structure":
        return "Technical Structure", "Summarizes trend state, breakout quality, and whether price action is improving or degrading."
    if agent == "macro_event":
        return "Event Risk", "Flags whether the next few sessions are loaded with macro catalysts that can distort or accelerate moves."
    if agent == "earnings_revision":
        return "Earnings Tone", "Approximates whether earnings reactions are being rewarded or faded across sectors."
    if agent == "sector_internals":
        return "Sector Breadth", "Checks whether sector leadership is broad and healthy or narrow and concentration-driven."
    if agent == "options_proxy":
        return "Options Structure", "Reads the volatility and gamma backdrop to judge whether positioning is supportive, unstable, or squeeze-prone."
    return agent.replace("_", " ").title(), "Agent context layer."


def _agent_tone(summary: str) -> tuple[str, str]:
    """Infer a simple tone tag from the summary text."""
    text = (summary or "").lower()
    if any(token in text for token in ["risk_off", "fragility", "credit stress", "negative", "downtrend", "unstable", "defensive", "capital preservation"]):
        return "Caution", "#b42318"
    if any(token in text for token in ["supportive", "positive", "improving", "uptrend", "lead", "healthy", "favorable"]):
        return "Supportive", "#1f7a3d"
    return "Mixed", "#f59e0b"


def _render_agent_narratives(agent_results: dict) -> None:
    """Render narrative summaries for the main agents."""
    st.markdown("### Narrative Summary")
    st.caption("A more readable interpretation of each agent, meant for quick daily review before drilling into tables and charts.")
    preferred_order = [
        "macro_regime",
        "liquidity_rates_credit",
        "sentiment_internals",
        "technical_structure",
        "cross_asset_leadlag",
        "macro_event",
        "earnings_revision",
        "sector_internals",
        "options_proxy",
        "seasonality",
    ]
    cards = [name for name in preferred_order if name in agent_results]
    rows = [cards[i : i + 2] for i in range(0, len(cards), 2)]
    for row in rows:
        cols = st.columns(len(row))
        for col, agent_name in zip(cols, row, strict=False):
            result = agent_results[agent_name]
            summary = result.get("summary", "") if isinstance(result, dict) else getattr(result, "summary", "")
            title, framing = _agent_narrative(agent_name, summary)
            tone, color = _agent_tone(summary)
            col.markdown(
                f"""
                <div style="border:1px solid #d0d5dd;border-radius:12px;padding:14px 16px;background:#ffffff;min-height:180px;">
                  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;">
                    <div style="font-size:17px;font-weight:700;color:#101828;">{title}</div>
                    <span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{color};color:white;font-size:12px;font-weight:700;">{tone}</span>
                  </div>
                  <div style="font-size:13px;color:#475467;margin-bottom:10px;line-height:1.45;">{framing}</div>
                  <div style="font-size:14px;color:#344054;line-height:1.55;">{summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_overview(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Overview", SECTION_HELP["Overview"])
    _render_market_posture_banner(payload)
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    _render_semaphore_row(payload)
    agent_results = payload.get("agent_results", {})
    _render_agent_narratives(agent_results)

    sectors = _with_asset_category(frame_from_payload(payload, "top_ranked_sectors"), project_root)
    opportunities = _with_asset_category(frame_from_payload(payload, "opportunity_table"), project_root)
    validation = frame_from_payload(payload, "validation_table")
    unstable = frame_from_payload(payload, "unstable_proxies_table")
    buy_candidates, sell_candidates = _build_research_actions(opportunities, validation, unstable)

    st.markdown("### What To Buy / What To Sell")
    st.caption("Research candidates only. These are context-aware ideas generated from opportunity, proxy validation, and fragility signals, not automated execution advice.")
    action_tabs = st.tabs(["What To Buy", "What To Sell"])
    with action_tabs[0]:
        if not buy_candidates.empty:
            buy_plot = buy_candidates.copy()
            fig = px.bar(
                buy_plot.sort_values("action_score", ascending=True),
                x="action_score",
                y="ticker",
                color="asset_category",
                orientation="h",
                title="What To Buy: Highest Contextual Proxy Success",
                hover_data=["name", "opportunity_label", "early_opportunity_score", "proxy_stability"],
            )
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="Category")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_action_cards("What To Buy", buy_candidates, "#1f7a3d")
    with action_tabs[1]:
        if not sell_candidates.empty:
            sell_plot = sell_candidates.copy()
            fig = px.bar(
                sell_plot.sort_values("action_score", ascending=True),
                x="action_score",
                y="ticker",
                color="asset_category",
                orientation="h",
                title="What To Sell: Weakest Contextual Proxy Success",
                hover_data=["name", "opportunity_label", "early_opportunity_score", "proxy_stability"],
            )
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="Category")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_action_cards("What To Sell", sell_candidates, "#b42318")

    st.markdown("---")
    ranking_tabs = st.tabs(["Top Sectors", "Top Early Opportunities"])
    with ranking_tabs[0]:
        st.subheader("Top Sectors")
        if not sectors.empty:
            sector_plot = sectors.copy()
            sector_plot["display_label"] = sector_plot["ticker"] + " | " + sector_plot["asset_category"]
            fig = px.bar(
                sector_plot.head(10).sort_values("score", ascending=True),
                x="score",
                y="display_label",
                color="asset_category",
                orientation="h",
                title="Sector / Macro Leadership Snapshot",
                hover_data=["ticker", "name", "classification", "relative_strength_20d", "trend_quality", "rsi"],
            )
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="Category")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(
                sectors[["ticker", "name", "asset_category", "score", "classification"]].head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No sector ranking available.")
    with ranking_tabs[1]:
        st.subheader("Top Early Opportunities")
        if not opportunities.empty:
            opp_plot = opportunities.copy()
            opp_plot["display_label"] = opp_plot["ticker"] + " | " + opp_plot["asset_category"]
            opp_plot["bubble_size"] = pd.to_numeric(opp_plot.get("trend_quality", 0), errors="coerce").fillna(0).clip(lower=0) + 8
            fig = px.scatter(
                opp_plot.head(12),
                x="relative_strength_20d",
                y="early_opportunity_score",
                color="asset_category",
                size="bubble_size",
                hover_name="ticker",
                hover_data=["name", "opportunity_label", "relative_strength_60d", "technical_state", "proxy_stability"],
                title="Early Opportunity Map",
            )
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), legend_title_text="Category")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(
                opportunities[["ticker", "name", "asset_category", "early_opportunity_score", "opportunity_label"]].head(12),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No opportunity ranking available.")

    baskets = load_latest_baskets(project_root, weekly=weekly)
    if baskets:
        name = st.selectbox("Basket snapshot", list(baskets.keys()))
        st.dataframe(baskets[name], use_container_width=True, hide_index=True)


def _render_what_changed(payload: dict, project_root: Path, weekly: bool) -> None:
    changed = load_what_changed(project_root, weekly=weekly)
    _section_header("What Changed", SECTION_HELP["What Changed"])
    transitions = changed.get("transitions", pd.DataFrame())
    change_log = changed.get("change_log", {})
    proxy_text = str(change_log.get("proxy_deterioration", ""))
    ranking_text = str(change_log.get("ranking_transitions", ""))
    deterioration_df = _parse_proxy_deterioration(proxy_text)

    top = st.columns(3)
    top[0].metric("State Transitions", f"{len(transitions)}")
    top[1].metric("Weakening Proxies", f"{len(deterioration_df)}")
    top[2].metric("Payload Mode", "Weekly" if weekly else "Daily")

    summary_cols = st.columns(2)
    with summary_cols[0].container(border=True):
        st.markdown("#### Key Takeaways")
        if ranking_text:
            st.write(f"- Ranking shifts: {ranking_text}")
        else:
            st.write("- No ranking-state changes detected in the current comparison window.")
        if proxy_text:
            st.write(f"- Proxy deterioration: {proxy_text}")
        else:
            st.write("- No proxy deterioration summary was generated.")
    with summary_cols[1].container(border=True):
        st.markdown("#### Interpretation")
        if not transitions.empty:
            st.write("Ranking states changed versus the previous run, which usually means leadership or opportunity quality is moving, not just noise in the same regime.")
        elif not deterioration_df.empty:
            st.write("No category transitions were recorded, but underlying proxy quality weakened. This often means the surface ranking is stable while confirmation is softening underneath.")
        else:
            st.write("The current run looks broadly stable relative to the previous snapshot. That can be useful when you want confirmation rather than churn.")

    visual_cols = st.columns(2)
    if not deterioration_df.empty:
        det_plot = deterioration_df.sort_values("delta")
        fig = px.bar(
            det_plot,
            x="delta",
            y="proxy",
            orientation="h",
            color="delta",
            color_continuous_scale=["#b42318", "#f59e0b", "#1f7a3d"],
            title="Proxy Stability Change vs Previous Run",
            hover_data=["previous", "current"],
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), coloraxis_showscale=False)
        visual_cols[0].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        visual_cols[0].info("No proxy deterioration series available for this run.")

    if not transitions.empty:
        transition_plot = transitions.copy()
        transition_plot["transition"] = transition_plot["previous_value"] + " → " + transition_plot["current_value"]
        transition_plot["count"] = 1
        fig = px.bar(
            transition_plot,
            x="item",
            y="count",
            color="transition",
            title="Ranking State Transitions",
            hover_data=["item", "previous_value", "current_value", "summary"],
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="", xaxis_title="")
        visual_cols[1].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        visual_cols[1].info("No ranking-state transitions detected.")

    lower_cols = st.columns(2)
    with lower_cols[0]:
        st.markdown("#### Proxy Deterioration Table")
        if not deterioration_df.empty:
            st.dataframe(deterioration_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Empty because no proxy deterioration block was parsed for this payload.")
    with lower_cols[1]:
        st.markdown("#### Transition Table")
        if not transitions.empty:
            st.dataframe(transitions, use_container_width=True, hide_index=True)
        else:
            st.caption("No ranking transitions were recorded for this snapshot.")


def _render_baskets(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Candidate Baskets", SECTION_HELP["Candidate Baskets"])
    baskets = load_latest_baskets(project_root, weekly=weekly)
    if not baskets:
        st.info("No baskets persisted yet.")
        return
    portfolio_summary = payload.get("portfolio_summary", {})
    for name, basket in baskets.items():
        st.markdown(f"#### {name}")
        st.dataframe(basket, use_container_width=True, hide_index=True)
        summary = portfolio_summary.get(name, {})
        if summary:
            cols = st.columns(4)
            _kpi_metric(cols[0], "Basket Return", f"{summary.get('basket_return', 0):.1f}%")
            _kpi_metric(cols[1], "Relative", f"{summary.get('relative_return', 0):.1f}%")
            _kpi_metric(cols[2], "Drawdown", f"{summary.get('basket_drawdown', 0):.1f}%")
            _kpi_metric(cols[3], "Turnover", f"{summary.get('turnover_estimate', 0):.3f}")


def _render_exposure(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Exposure Model", SECTION_HELP["Exposure Model"])
    exposure = payload.get("exposure_view", {})
    st.write(exposure.get("exposure_summary", "No exposure view available."))
    components = pd.DataFrame(
        [{"component": key, "score": value} for key, value in exposure.get("supporting_components", {}).items()]
    )
    st.dataframe(components, use_container_width=True, hide_index=True)
    if not components.empty:
        fig = px.bar(components, x="component", y="score", title="Exposure Supporting Components")
        st.plotly_chart(fig, use_container_width=True)
    history = load_score_history_frame(project_root, "breadth_score")
    if not history.empty:
        fig = px.line(history, x="timestamp", y="score_value", color="agent_name", title="Breadth Score History")
        st.plotly_chart(fig, use_container_width=True)


def _render_proxy_health(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Proxy Health", SECTION_HELP["Proxy Health"])
    validation = frame_from_payload(payload, "validation_table")
    unstable = frame_from_payload(payload, "unstable_proxies_table")
    st.dataframe(validation, use_container_width=True, hide_index=True)
    st.markdown("#### Unstable Proxies")
    st.dataframe(unstable, use_container_width=True, hide_index=True)
    transitions = load_transition_history(project_root, limit=100)
    if not transitions.empty:
        st.markdown("#### Recent Ranking Transitions")
        st.dataframe(transitions, use_container_width=True, hide_index=True)


def _render_run_history(project_root: Path) -> None:
    _section_header("Run History", SECTION_HELP["Run History"])
    history = load_run_history(project_root, limit=50)
    st.dataframe(history, use_container_width=True, hide_index=True)
    if not history.empty:
        fig = px.line(history.sort_values("timestamp"), x="timestamp", y="spx_regime_score", color="run_type", title="SPX Regime Score History")
        st.plotly_chart(fig, use_container_width=True)


def _render_alerts(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Alert Center", SECTION_HELP["Alert Center"])
    alerts = frame_from_payload(payload, "alerts_table")
    st.dataframe(alerts, use_container_width=True, hide_index=True)
    alert_history = load_alert_history(project_root, limit=100)
    st.markdown("#### Alert History")
    st.dataframe(alert_history, use_container_width=True, hide_index=True)
    watchlist = frame_from_payload(payload, "watchlist_table")
    st.markdown("#### Watchlist")
    st.dataframe(watchlist, use_container_width=True, hide_index=True)


def _render_exports(project_root: Path) -> None:
    _section_header("Quick Exports", SECTION_HELP["Quick Exports"])
    export_dir = project_root / "outputs" / "exports"
    if not export_dir.exists():
        st.info("No exports created yet.")
        return
    export_files = sorted(path for path in export_dir.iterdir() if path.is_file())
    for path in export_files:
        st.write(path.name)


def _generate_payload(project_root: Path, weekly: bool) -> None:
    """Generate a payload for first-run or hosted deployments."""
    config = load_config_bundle(project_root / "config")
    if weekly:
        WeeklyCycleRunner(config=config, project_root=project_root).run()
    else:
        DailyCycleRunner(config=config, project_root=project_root).run(run_type="sample")


def _refresh_all_payloads(project_root: Path) -> None:
    """Refresh both dashboard payloads."""
    config = load_config_bundle(project_root / "config")
    DailyCycleRunner(config=config, project_root=project_root).run(run_type="sample")
    WeeklyCycleRunner(config=config, project_root=project_root).run()


def _ensure_payload(project_root: Path, weekly: bool) -> dict:
    """Load a payload and bootstrap one when missing."""
    payload = load_payload(project_root, weekly=weekly)
    if payload:
        return payload

    st.info("No saved payload found yet. Generating a sample research snapshot for the dashboard.")
    if st.button("Generate dashboard data", type="primary", use_container_width=False):
        with st.spinner("Running the research engine and building the initial payload..."):
            _generate_payload(project_root, weekly=weekly)
        st.rerun()
    return {}


def main() -> None:
    """Render the local dashboard."""
    project_root = PROJECT_ROOT
    st.set_page_config(
        page_title="Market Intelligence Operations Console",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_responsive_styles()
    st.title("Market Intelligence Operations Console")

    run_type = st.sidebar.selectbox("Payload", ["daily", "weekly"])
    page = st.sidebar.radio(
        "Page",
        ["Overview", "What Changed", "Baskets", "Exposure", "Proxy Health", "Run History", "Alerts", "Exports"],
    )
    payload = _ensure_payload(project_root, weekly=run_type == "weekly")
    if not payload:
        return
    _mode_badge(run_type, str(payload.get("timestamp", "n/a")))
    _refresh_controls(project_root)

    if page == "Overview":
        _render_overview(payload, project_root, weekly=run_type == "weekly")
    elif page == "What Changed":
        _render_what_changed(payload, project_root, weekly=run_type == "weekly")
    elif page == "Baskets":
        _render_baskets(payload, project_root, weekly=run_type == "weekly")
    elif page == "Exposure":
        _render_exposure(payload, project_root, weekly=run_type == "weekly")
    elif page == "Proxy Health":
        _render_proxy_health(payload, project_root, weekly=run_type == "weekly")
    elif page == "Run History":
        _render_run_history(project_root)
    elif page == "Alerts":
        _render_alerts(payload, project_root, weekly=run_type == "weekly")
    else:
        _render_exports(project_root)


if __name__ == "__main__":
    main()
