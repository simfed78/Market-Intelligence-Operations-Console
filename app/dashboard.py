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


def _refresh_controls(project_root: Path, weekly: bool) -> None:
    """Render dashboard refresh actions."""
    cols = st.columns([0.22, 0.78])
    button_label = "Refresh weekly data" if weekly else "Refresh daily data"
    help_text = "Run the full weekly cycle and refresh the hosted payload." if weekly else "Run the daily sample cycle and refresh the dashboard payload."
    if cols[0].button(button_label, help=help_text, use_container_width=True):
        with st.spinner("Refreshing dashboard data..."):
            _generate_payload(project_root, weekly=weekly)
        st.success("Refresh completed.")
        st.rerun()
    cols[1].caption("Use this when you want to rebuild the current dashboard snapshot without leaving Streamlit.")


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
    rows = [items[i : i + 4] for i in range(0, len(items), 4)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, raw_value, state, color) in zip(cols, row, strict=False):
            _render_gauge(col, label, float(raw_value), color, state)


def _kpi_metric(container, label: str, value: str) -> None:
    container.metric(label, value, help=KPI_HELP.get(label))


def _metric_row(payload: dict) -> None:
    scores = payload.get("scores", {})
    exposure = payload.get("exposure_view", {})
    cols = st.columns(5)
    _kpi_metric(cols[0], "SPX Regime", f"{scores.get('spx_regime_score', 0):.1f}")
    _kpi_metric(cols[1], "Sector Opportunity", f"{scores.get('sector_opportunity_score', 0):.1f}")
    _kpi_metric(cols[2], "Cyclical Opportunity", f"{scores.get('cyclical_opportunity_score', 0):.1f}")
    _kpi_metric(cols[3], "Risk Flag", payload.get("risk_environment_flag", "unknown"))
    _kpi_metric(cols[4], "Exposure", exposure.get("exposure_stance_label", "n/a"))


def _render_overview(payload: dict, project_root: Path, weekly: bool) -> None:
    _section_header("Overview", SECTION_HELP["Overview"])
    _render_semaphore_row(payload)
    _metric_row(payload)
    agent_results = payload.get("agent_results", {})
    summary_df = pd.DataFrame(
        [{"agent": name, "summary": data.get("summary", "")} for name, data in agent_results.items()]
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    sectors = _with_asset_category(frame_from_payload(payload, "top_ranked_sectors"), project_root)
    opportunities = _with_asset_category(frame_from_payload(payload, "opportunity_table"), project_root)
    cols = st.columns(2)
    cols[0].subheader("Top Sectors")
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
        cols[0].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        cols[0].dataframe(
            sectors[["ticker", "name", "asset_category", "score", "classification"]].head(10),
            use_container_width=True,
            hide_index=True,
        )
    else:
        cols[0].info("No sector ranking available.")
    cols[1].subheader("Top Early Opportunities")
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
        cols[1].plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        cols[1].dataframe(
            opportunities[["ticker", "name", "asset_category", "early_opportunity_score", "opportunity_label"]].head(12),
            use_container_width=True,
            hide_index=True,
        )
    else:
        cols[1].info("No opportunity ranking available.")

    baskets = load_latest_baskets(project_root, weekly=weekly)
    if baskets:
        name = st.selectbox("Basket snapshot", list(baskets.keys()))
        st.dataframe(baskets[name], use_container_width=True, hide_index=True)


def _render_what_changed(payload: dict, project_root: Path, weekly: bool) -> None:
    changed = load_what_changed(project_root, weekly=weekly)
    _section_header("What Changed", SECTION_HELP["What Changed"])
    for key, value in changed.get("change_log", {}).items():
        st.write(f"- {key}: {value}")
    transitions = changed.get("transitions", pd.DataFrame())
    st.dataframe(transitions, use_container_width=True, hide_index=True)
    if not transitions.empty:
        fig = px.histogram(transitions, x="current_value", color="previous_value", title="Ranking State Transitions")
        st.plotly_chart(fig, use_container_width=True)


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
    st.set_page_config(page_title="Market Intelligence Operations Console", layout="wide")
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
    _refresh_controls(project_root, weekly=run_type == "weekly")

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
