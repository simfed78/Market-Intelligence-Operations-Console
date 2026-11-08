"""Private, research-only multi-asset console; no broker or legacy workflow imports."""

from __future__ import annotations

from pathlib import Path
import sys
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.service import load_dashboard
from src.intelligence.store import Store
from src.intelligence.hosted import start_public_refresh, public_status
from src.intelligence.opportunities import rank_opportunities, top10, MODEL_VERSION, WEIGHTS
from app.fineco_workspace import fineco_workspace

GREEN = "#1f4f46"
AMBER = "#ad7529"
RED = "#ad4b48"
COLORS = [GREEN, "#758eab", AMBER, "#8d76a2", "#73a198", RED, "#7d8165"]
APP_RELEASE = "2B.3-FINECO-2026-11-08"
VIEWS = ["Overview", "Fineco · Piano operativo", "Asset explorer", "Capital flows", "Macro & relative value", "Trading Desk monitor", "Data quality"]
HORIZONS = {"1 mese": ("momentum_1m", "ret_21"), "3 mesi": ("momentum_3m", "ret_63"), "6 mesi": ("momentum_6m", "ret_126"), "12 mesi": ("momentum_12m", "ret_252")}
READINESS_ORDER = {"research candidate": 2, "watch": 1, "blocked": 0}


@st.cache_data(ttl=30, show_spinner=False)
def _load(root: str) -> dict:
    return load_dashboard(Path(root))


def _frame(value) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def _number(value, pct: bool = False) -> str:
    try:
        value = float(value)
        if not np.isfinite(value):
            return "—"
        return f"{value * 100:+.2f}%" if pct else f"{value:,.2f}"
    except (TypeError, ValueError):
        return "—"


def _styles() -> None:
    st.markdown("""<style>
    .stApp [data-testid="stAppViewContainer"] {background:#fcfcf9;}
    .stApp h1,.stApp h2,.stApp h3 {letter-spacing:-.025em;}
    .stApp [data-testid="stMetric"] {border:1px solid #e0e7e2;border-radius:12px;padding:.8rem;background:#fff;}
    .stApp [data-testid="stSidebar"] {border-right:1px solid #dfe6df;}
    .stApp [data-testid="stDataFrame"] {border-radius:10px;}
    .stApp .block-container {padding-top:2rem;padding-bottom:3rem;max-width:1600px;}
    @media(max-width:700px){.stApp .block-container{padding:1rem .8rem 2rem;}.stApp h1{font-size:1.65rem;line-height:1.15;} .stApp h2{font-size:1.35rem;}}
    </style>""", unsafe_allow_html=True)


def _plot(fig, key: str, height: int = 360) -> None:
    fig.update_layout(
        height=height, template="plotly_white", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font={"color": "#14221f"},
        margin={"l": 10, "r": 15, "t": 25, "b": 15},
        legend={"orientation": "h", "y": 1.1, "x": 0},
        colorway=COLORS, hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e7ece7", zerolinecolor="#c6d0c9")
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def _table(frame: pd.DataFrame, columns: list[str] | None = None, key: str | None = None) -> None:
    if frame.empty:
        st.info("Nessuna osservazione disponibile per questi filtri.")
        return
    shown = frame[[c for c in columns if c in frame.columns]] if columns else frame
    config = {
        "symbol": st.column_config.TextColumn("Simbolo", pinned=True),
        "name": "Strumento", "asset_class": "Asset class", "region": "Area", "kind": "Tipo",
        "currency": "Valuta", "price_status": "Prezzi", "volume_status": "Volumi",
        "source_url": st.column_config.LinkColumn("Fonte"),
        "ret_21": st.column_config.NumberColumn("1 mese", format="percent"),
        "ret_63": st.column_config.NumberColumn("3 mesi", format="percent"),
        "ret_252": st.column_config.NumberColumn("12 mesi", format="percent"),
        "drawdown_sample": st.column_config.NumberColumn("Drawdown campione", format="percent"),
        "momentum_1m": st.column_config.NumberColumn("Momentum 1m", format="%.1f"),
        "ret_126": st.column_config.NumberColumn("6 mesi",format="percent"),
        "momentum_6m": st.column_config.NumberColumn("Momentum 6m",format="%.1f"),
        "momentum_3m": st.column_config.NumberColumn("Momentum 3m", format="%.1f"),
        "momentum_12m": st.column_config.NumberColumn("Momentum 12m", format="%.1f"),
        "timing_score": st.column_config.NumberColumn("Conferma tecnica", format="%.1f"),
        "risk_score": st.column_config.NumberColumn("Rischio", format="%.1f"),
        "opportunity_score": st.column_config.NumberColumn("Opportunity score", format="%.1f"),
        "technical_score": st.column_config.NumberColumn("Score tecnico", format="%.1f"),
        "momentum": st.column_config.NumberColumn("Momentum", format="%.1f"),
        "readiness": st.column_config.NumberColumn("Prontezza", format="%.0f"),
        "status": "Stato", "driver": "Driver", "liquidity": "Liquidità", "flow_data_quality": "Qualità flow",
        "priority_reason": "Motivo priorità", "technical_levels": "Livelli tecnici verificati",
        "entry_assessment": "Valutazione ingresso", "source": "Fonte",
        "score_change": st.column_config.NumberColumn("Δ score", format="%+.1f"),
        "rvol_5": st.column_config.NumberColumn("RVOL 5", format="%.2fx"),
        "rvol_20": st.column_config.NumberColumn("RVOL 20", format="%.2fx"),
        "rvol_60": st.column_config.NumberColumn("RVOL 60", format="%.2fx"),
        "volume_z60": st.column_config.NumberColumn("Z-score volume 60", format="%.2f"),
        "obv_change20": st.column_config.NumberColumn("Variation OBV 20", format="compact"),
        "cmf20": st.column_config.NumberColumn("Chaikin MF 20", format="%.3f"),
        "data_confidence": "Qualità evidenza", "reason": "Spiegazione",
        "observed_at": "Osservazione", "available_at": "Disponibilità", "retrieved_at": "Acquisizione",
    }
    st.dataframe(shown, column_config=config, hide_index=True, width="stretch", key=key)


def _history(histories: dict, symbol: str) -> pd.DataFrame:
    frame = _frame(histories.get(symbol))
    if frame.empty:
        return frame
    if "date" not in frame.columns:
        frame = frame.reset_index().rename(columns={frame.index.name or "index": "date"})
    if "date" not in frame.columns:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    return frame.dropna(subset=["date"]).sort_values("date")


def _comparison(histories: dict, symbols: list[str], days: int, key: str) -> None:
    series = []
    for symbol in symbols:
        frame = _history(histories, symbol)
        if frame.empty or "adj_close" not in frame:
            continue
        part = frame.set_index("date")["adj_close"].rename(symbol)
        # Align sessions, not exchange opening timestamps. Never fill missing prices.
        part.index = part.index.normalize()
        if part.index.has_duplicates:
            continue
        series.append(part)
    if not series:
        st.info("Serie rettificate non disponibili per il confronto.")
        return
    combined = pd.concat(series, axis=1, join="inner").tail(days).dropna(how="any")
    if len(combined) < 2 or (combined.iloc[0] <= 0).any():
        st.info("Servono almeno due sedute comuni con prezzi rettificati disponibili.")
        return
    rebased = combined / combined.iloc[0] * 100
    fig = px.line(rebased, labels={"value": "Base 100", "date": "", "variable": "Strumento"})
    _plot(fig, key)
    st.caption(f"Base 100 · {combined.index[0]:%d/%m/%Y}–{combined.index[-1]:%d/%m/%Y} · solo sedute comuni. Rendimenti nella valuta di quotazione; nessuna conversione valutaria.")


def _finite(value) -> float | None:
    try:
        number = float(value)
        return number if np.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _technical_levels(row: pd.Series, histories: dict) -> str:
    """Return only price levels reproducible from the validated daily series."""
    if str(row.get("price_status", "")) != "VALID":
        return "Non verificati: prezzi non VALID"
    history = _history(histories, str(row.get("symbol", "")))
    if history.empty or "close" not in history:
        return "Non verificati: storico close assente"
    close = pd.to_numeric(history["close"], errors="coerce").dropna()
    if len(close) < 200:
        return "Non verificati: meno di 200 sedute"
    last, sma50, sma200 = close.iloc[-1], close.tail(50).mean(), close.tail(200).mean()
    if not np.isfinite([last, sma50, sma200]).all():
        return "Non verificati: serie non finita"
    return f"Close {last:,.2f} · SMA50 {sma50:,.2f} · SMA200 {sma200:,.2f}"


def _open_asset(symbol: str) -> None:
    st.session_state["selected_asset"] = symbol
    st.session_state["workspace"] = "Asset explorer"


def _ranked(data: dict, score: str) -> pd.DataFrame:
    horizon=score.removeprefix("momentum_")
    ranked=(data.get("opportunities") or {}).get(horizon)
    if isinstance(ranked,pd.DataFrame):return ranked.copy()
    metrics=_frame(data.get('metrics'))
    if metrics.empty:
        metrics=_frame(data.get('universe'))
        metrics['price_status']='MISSING'
        metrics['ranking_eligible']=False
    return rank_opportunities(metrics,horizon)


def _compact_default() -> bool:
    try:
        agent=st.context.headers.get('User-Agent','').lower()
        return 'iphone' in agent or 'android' in agent
    except (AttributeError,RuntimeError,KeyError):return False


def _opportunity_cards(frame: pd.DataFrame, key: str) -> None:
    for row in frame.to_dict('records'):
        with st.container(border=True):
            st.markdown(f"**{row['priority']}. {row['symbol']}** · {row.get('subcategory',row.get('asset_class',''))}")
            st.caption(str(row.get('name','')))
            action='Da approfondire' if row.get('signal_state')=='RESEARCH CANDIDATE' else 'Attendere conferma'
            st.write(f"{action} · {row.get('horizon','')} · rischio volatilità {row.get('risk_category','—')}")
            price=_finite(row.get('price'));ma=_finite(row.get('sma50'))
            if price is not None:
                st.caption(f"Chiusura {price:,.2f} {row.get('currency','')} · seduta {row.get('observed_at','—')}")
            if price is not None and ma is not None:
                st.write(f"{'Sopra' if price>ma else 'Sotto'} la media a 50 sedute ({ma:,.2f}).")
            st.caption(str(row.get('rationale','')))
            st.button('Apri scheda',key=f"{key}_card_{row['symbol']}",on_click=_open_asset,args=(row['symbol'],))


@st.fragment(run_every='3s')
def _refresh_notice() -> None:
    state=public_status(PROJECT_ROOT)
    status=state.get('status')
    if status=='RUNNING':
        completed=state.get('completed',0);total=max(state.get('total',153),1)
        st.progress(min(completed/total,1.0),text=f"Caricamento dati: {completed}/{total} fonti verificate")
        st.caption('Aggiornamento in corso. La pagina si aggiorna da sola al termine; eventuali dati precedenti restano visibili.')
    elif status in ('COMPLETE','FAILED'):
        job=state.get('job_id')
        if job and st.session_state.get('completed_refresh_id')!=job:
            st.session_state['completed_refresh_id']=job
            _load.clear()
            st.rerun()
        result=state.get('result',{})
        errors=result.get('errors',[])
        if errors:
            st.caption(f"Aggiornamento concluso: {result.get('acquired',0)} fonti scaricate, {result.get('cached',0)} in cache, {len(errors)} non aggiornate. Dettagli nel menu Data quality.")


def _ranking_table(frame: pd.DataFrame, key: str) -> None:
    compact=st.checkbox('Vista compatta',value=_compact_default(),key=key+'_compact')
    if compact:
        _opportunity_cards(frame,key)
        return
    columns=["priority","symbol","name","asset_class","subcategory","opportunity_score","rank_change",
             "ret_21","ret_63","ret_126","ret_252","volume_signal","risk_category","horizon","signal_state","rationale","observed_at","updated_at"]
    config={"priority":st.column_config.NumberColumn("Priorità",pinned=True),
            "symbol":st.column_config.TextColumn("Ticker",pinned=True),"name":"Nome completo",
            "asset_class":"Asset class","subcategory":"Sottocategoria",
            "opportunity_score":st.column_config.ProgressColumn("Opportunity · tecnico",min_value=0,max_value=100,format="%.1f"),
            "rank_change":st.column_config.NumberColumn("Δ rank globale",format="%+d"),
            "ret_21":st.column_config.NumberColumn("Momentum 1m",format="percent"),
            "ret_63":st.column_config.NumberColumn("3m",format="percent"),
            "ret_126":st.column_config.NumberColumn("6m",format="percent"),
            "ret_252":st.column_config.NumberColumn("12m",format="percent"),
            "risk_category":"Rischio volatilità","horizon":"Orizzonte","signal_state":"Stato",
            "rationale":"Perché è selezionato","observed_at":"Seduta","updated_at":"Acquisizione"}
    event=st.dataframe(frame[[c for c in columns if c in frame]],column_config=config,
             hide_index=True,width="stretch",height=min(425,55+len(frame)*35),
             on_select="rerun",selection_mode="single-row",key=key)
    if event.selection.rows:
        st.session_state["detail_selection"]=frame.iloc[event.selection.rows[0]].symbol
    options=frame.symbol.tolist()
    selected=st.session_state.get("detail_selection")
    index=options.index(selected) if selected in options else 0
    choice=st.selectbox("Apri una scheda strumento",options,index=index,
                        format_func=lambda x:f"{x} · {frame.set_index('symbol').loc[x,'name']}",key=key+"_detail")
    st.button("Apri analisi completa",key=key+"_open",on_click=_open_asset,args=(choice,))


def _overview(data: dict, filtered: pd.DataFrame, score: str, return_col: str) -> None:
    st.subheader("Global Macro & Risk Regime")
    macro=data.get("macro",{}) or {}
    label=str(macro.get("label","Non disponibile"))
    valid=int(filtered.price_status.eq('VALID').sum())
    st.caption(f"{label} · macro {macro.get('status','MISSING')} · prezzi validi {valid}/{len(filtered)} · ingressi validati 0")
    with st.expander('Dettagli del contesto macro'):
        st.write(str(macro.get('reason','Fonti macro mancanti.')))
    st.subheader("Top 10 Multi-Asset Opportunities")
    st.caption("Candidati di ricerca, non acquisti validati. La posizione tecnica nel gruppo non misura il rendimento atteso.")
    ranked=_ranked(data,score)
    universe_symbols=set(filtered.symbol)
    scope=ranked[ranked.symbol.isin(universe_symbols)].copy()
    risk=st.session_state.get("risk_filter",["Basso","Medio","Alto","Non determinabile"])
    scope=scope[scope.risk_category.isin(risk)]
    if st.session_state.get("early_filter",False):scope=scope[scope.early_opportunity.eq(True)]
    states=st.session_state.get("signal_filter",["RESEARCH CANDIDATE","WATCHLIST","ENTRY CANDIDATE"])
    scope=scope[scope.signal_state.isin(states)]
    top=top10(scope)
    if top.empty:
        st.info("Nessuna opportunità supera questi filtri e i controlli. Nessun valore neutrale sostituisce i fattori mancanti.")
    else:
        _ranking_table(top,"top_opportunities")
    with st.expander("Come leggere il ranking e i quattro stati"):
        st.write("Technical Score: media pesata dei quattro indici di momentum, con pesi diversi per asset class e orizzonte. Opportunity Score: 100 × (rango medio entro classe − 1)/(numero peer − 1), con almeno tre peer validi. Pesi non ottimizzati retrospettivamente e non calibrati sui rendimenti futuri. A parità di percentile, ordine deterministico per asset class e ticker.")
        st.write("RESEARCH CANDIDATE: Technical Score ≥60 e conferma tecnica ≥50. WATCHLIST: dati sufficienti, condizioni tecniche ancora deboli. BLOCKED: dati essenziali non validi, benchmark non negoziabile o meno di tre peer. ENTRY CANDIDATE: riservato a un modello di ingresso validato; attualmente nessuno. Un gate Core aperto non valida questo modello.")
        st.write("I filtri non ricalcolano i percentili. La priorità 1–10 è la coda nel filtro; Δ rank confronta i ranghi globali a parità di modello, orizzonte e copertura. Un trattino significa che non esiste un confronto valido, non variazione zero. Rischio basso/medio/alto descrive soltanto la volatilità storica normalizzata.")
        _table(top,["symbol","technical_score","opportunity_score","macro_alignment","relative_value_score","capital_flow_score","risk_score","data_confidence","included_factors","peer_count","entry_validation"],"factor_breakdown")
    st.subheader("Emerging Opportunities / Capital Flow Radar")
    early=scope[scope.early_opportunity.eq(True)]
    st.caption("Early Opportunity sperimentale: rialzo ancora contenuto, RVOL20 ≥1,2, OBV20 e CMF20 positivi, forza relativa a 63 sedute in miglioramento. È una combinazione descrittiva di prezzo e volume; capacità predittiva non validata, nessuna deduzione di acquisti istituzionali.")
    if early.empty:
        st.info("Nessuna Early Opportunity confermata dalle regole descrittive nei dati e filtri correnti.")
    else:
        _table(early,["symbol","name","ret_21","rvol_20","volume_z60","obv_change20","cmf20","rs_improvement","accumulation","observed_at"],"early_radar")
    _table(scope[scope.volume_signal.eq('Volume anomalo')].head(8),["symbol","name","rvol_20","volume_z60","volume_signal","price_volume_divergence"],"volume_radar")
    st.subheader("Equity vs Bonds Relative Value")
    observations=_frame(macro.get("observations"))
    if not observations.empty:
        rates=observations[observations.series.isin(["DGS10","DFII10","T10YIE","BAMLC0A0CM","BAMLH0A0HYM2"])]
        _table(rates,["name","value","unit","status","observed_at"],"relative_value_rates")
    st.caption("Rendimenti reali/nominali, inflazione implicita e spread credito sono contesto. Earnings yield, term premium e duration non sono qualificati: Relative Value Score MISSING. Nessuna graduatoria equity/bond viene inventata.")
    compare=[s for s in ["SPY","IEF","TLT"] if s in universe_symbols]
    _comparison(data.get("histories",{}),compare,252,"overview_equity_bonds")
    st.subheader("Market Risk & Vulnerabilities")
    weak=scope[scope.signal_state.ne('BLOCKED')].sort_values(["opportunity_score","symbol"]).head(5)
    _table(weak,["symbol","name","asset_class","technical_score","risk_category","drawdown_sample","signal_state"],"vulnerabilities")
    blocked=ranked[ranked.symbol.isin(universe_symbols)&ranked.signal_state.eq('BLOCKED')]
    with st.expander(f"Strumenti BLOCKED · {len(blocked)}"):
        _table(blocked,["symbol","name","price_status","volume_status","signal_state","rationale","reason"],"blocked_assets")


def _explorer(data: dict, filtered: pd.DataFrame) -> None:
    if filtered.empty:
        st.info("Seleziona almeno un asset nei filtri laterali.")
        return
    labels = dict(zip(filtered["symbol"], filtered["name"]))
    options=filtered["symbol"].tolist()
    selected=st.session_state.get("selected_asset")
    symbol = st.selectbox("Asset", options, index=options.index(selected) if selected in options else 0, format_func=lambda s: f"{s} · {labels.get(s, s)}")
    row = filtered[filtered["symbol"].eq(symbol)].iloc[0]
    st.caption(f"{row.get('kind', '—')} · {row.get('asset_class', '—')} · {row.get('region', '—')} · quotazione {row.get('currency', '—')}")
    registry = _frame(data.get("universe"))
    asset = registry[registry["symbol"].eq(symbol)] if not registry.empty and "symbol" in registry else pd.DataFrame()
    if not asset.empty and asset.iloc[0].get("exposure_note"):
        st.info(str(asset.iloc[0]["exposure_note"]))
    cols = st.columns(4)
    cols[0].metric("Ultima chiusura", _number(row.get("close", row.get("price")) ))
    cols[1].metric("1 mese", _number(row.get("ret_21"), True))
    cols[2].metric("3 mesi", _number(row.get("ret_63"), True))
    cols[3].metric("Dal massimo del campione", _number(row.get("drawdown_sample"), True))
    st.caption("Il massimo del campione non equivale al massimo storico assoluto (ATH). I rendimenti usano la serie rettificata del provider, ancora non certificata per il backtest Core.")
    frame = _history(data.get("histories", {}), symbol)
    days = st.select_slider("Sedute visualizzate", options=[63, 126, 252, 504], value=252)
    frame = frame.tail(days)
    if frame.empty or "close" not in frame:
        st.info("Storico prezzo non disponibile. La diagnostica dell’asset resta consultabile.")
    else:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.07, row_heights=[.76, .24])
        fig.add_trace(go.Scatter(x=frame["date"], y=frame["close"], name="Chiusura", line={"color": GREEN, "width": 2}), row=1, col=1)
        for length, color in [(20, AMBER), (50, "#758eab")]:
            # Compute on the displayed sample only; initial warmup remains visibly absent.
            fig.add_trace(go.Scatter(x=frame["date"], y=frame["close"].rolling(length).mean(), name=f"Media {length}", line={"color": color, "width": 1}), row=1, col=1)
        if "volume" in frame and frame["volume"].notna().any() and row.get("volume_status") != "MISSING":
            fig.add_trace(go.Bar(x=frame["date"], y=frame["volume"], name="Volume scambiato", marker_color="#829e94"), row=2, col=1)
        fig.update_yaxes(title_text=str(row.get("currency", "")), row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        _plot(fig, "asset_chart", 480)
    st.subheader("Confronto normalizzato")
    defaults = [s for s in [symbol, "SPY", "IEF"] if s in filtered["symbol"].values]
    compare = st.multiselect("Strumenti da confrontare", filtered["symbol"].tolist(), default=list(dict.fromkeys(defaults)), max_selections=6)
    _comparison(data.get("histories", {}), compare, days, "asset_comparison")
    st.subheader("Tesi di ricerca e condizioni")
    st.write(str(row.get("rationale","Dati non sufficienti per una tesi.")))
    st.caption(f"Stato: {row.get('signal_state','BLOCKED')} · Regime macro: {data.get('macro',{}).get('label','MISSING')}")
    _table(pd.DataFrame([row]),["symbol","benchmark","ret_21","ret_63","ret_126","ret_252","rs_21","rs_63","rs_improvement","rs_status"],"asset_relative_strength")
    _table(pd.DataFrame([row]),["symbol","technical_score","opportunity_score","macro_alignment","relative_value_score","capital_flow_score","risk_score","data_confidence","included_factors"],"asset_scores")
    st.write("**Fattori favorevoli:** " + ("medie mobili allineate; " if row.get('timing_score')==100 else "conferma tecnica incompleta; ") + str(row.get('accumulation','volume non qualificato')))
    st.write("**Fattori contrari:** valutazione, carry e flussi netti non qualificati; concentrazione/fattori sovrapposti da analizzare. " + str(row.get('exposure_note','')))
    _table(pd.DataFrame([row]),["sma50","sma200","support20","resistance20","breakout_confirmed","rvol_20","volume_z60","cmf20"],"asset_levels")
    st.info("Per considerare un ingresso: modello di ingresso validato, dati liquidi e aggiornati, trend e forza relativa confermati. Un superamento della resistenza delle 20 sedute precedenti è solo una conferma tecnica descrittiva. Perdita di SMA50/supporto20, peggioramento della forza relativa o dati degradati richiedono revisione della tesi. Nessuno stop o target automatico.")
    st.caption(str(row.get('entry_validation','MISSING · ingresso non validato')))
    _table(pd.DataFrame([row]), ["symbol", "price_status", "volume_status", "observed_at", "available_at", "retrieved_at", "source", "source_url"], "asset_sources")


def _flows(filtered: pd.DataFrame) -> None:
    st.subheader("Attività di mercato e divergenze")
    st.write("RVOL confronta il volume osservato con la sua base storica. Il volume scambiato misura attività, non afflussi netti né acquisti istituzionali.")
    st.caption("Gli indici e il forex possono non avere un volume centralizzato: il valore mancante resta MISSING.")
    measured = filtered[filtered.get("volume_status", pd.Series(dtype=str)).eq("VALID")].copy()
    if "rvol_20" in measured:
        values = measured.dropna(subset=["rvol_20", "ret_21"])
        if not values.empty:
            fig = px.scatter(values, x="ret_21", y="rvol_20", color="asset_class", hover_name="symbol", hover_data=["name"], color_discrete_sequence=COLORS)
            fig.add_hline(y=1, line_dash="dot", line_color="#929d94")
            fig.add_vline(x=0, line_dash="dot", line_color="#929d94")
            fig.update_xaxes(title="Performance 1 mese", tickformat="+.0%")
            fig.update_yaxes(title="RVOL 20")
            _plot(fig, "flow_scatter")
    _table(filtered, ["symbol", "name", "ret_21", "rvol_5", "rvol_20", "rvol_60", "volume_z60", "obv_change20", "cmf20", "volume_status", "observed_at"], "flow_table")
    st.caption("RVOL = volume dell’ultima seduta / media delle precedenti 5, 20 o 60 sedute. Lo z-score confronta lo stesso volume con media e deviazione standard delle precedenti 60. OBV 20 somma i volumi con segno della variazione del close; Chaikin MF usa close, massimi e minimi reali. Nessuno di questi indicatori misura flussi netti.")
    st.subheader("Copertura dei flussi")
    st.dataframe(pd.DataFrame([
        {"Dato": "ETF creazioni/rimborsi e flussi netti", "Stato": "MISSING", "Interpretazione": "Richiede una fonte dedicata; nessuna stima dal volume."},
        {"Dato": "Futures open interest e CFTC/COT", "Stato": "MISSING", "Interpretazione": "Integrazione prevista nel secondo incremento."},
        {"Dato": "Volume profile e POC", "Stato": "MISSING", "Interpretazione": "Servono dati intraday o per prezzo; nessun POC ricostruito da barre daily."},
        {"Dato": "Flow–Price Divergence", "Stato": "MISSING", "Interpretazione": "Indicatore sperimentale da definire e validare storicamente."},
    ]), hide_index=True, width="stretch")


def _macro(data: dict, filtered: pd.DataFrame) -> None:
    macro = data.get("macro", {}) or {}
    st.subheader("Regime macroeconomico")
    st.markdown(f"**{macro.get('label', 'Non disponibile')}** · `{macro.get('status', 'MISSING')}`")
    st.write(str(macro.get("reason", "La classificazione richiede osservazioni macro verificabili e date di disponibilità.")))
    observations = _frame(macro.get("observations"))
    _table(observations, key="macro_observations")
    st.subheader("Azioni e obbligazioni")
    candidates = [s for s in ["SPY", "IEF", "TLT", "LQD", "HYG", "TIP"] if s in filtered.get("symbol", pd.Series(dtype=str)).values]
    selected = st.multiselect("Proxy del confronto", candidates, default=candidates[:3], max_selections=6)
    _comparison(data.get("histories", {}), selected, 252, "equity_bonds")
    st.caption("Questo confronto descrive prezzi rettificati e rischio realizzato, non una stima dell’equity risk premium. I proxy in USD non rappresentano automaticamente il rendimento per un investitore in EUR.")
    with st.expander("Componenti di relative value da integrare", expanded=True):
        st.write("Earnings yield, aspettative sugli utili, rendimenti reali e nominali, term premium, spread IG/HY, duration e coperture valutarie devono avere fonti e qualità indipendenti. Lo score di valore relativo rimane MISSING finché queste componenti non sono disponibili.")
    st.subheader("Eventi macro e geopolitici")
    st.info("MISSING · Nessun feed di notizie verificato è collegato a questa vista. Gli eventi non vengono convertiti automaticamente in segnali.")


def _monitor(data: dict) -> None:
    st.subheader("Stato del Trading Desk Core")
    st.caption("Lettura di artifact locali sanitizzati. La dashboard non esegue il motore, non accede al broker e non modifica i gate.")
    core = data.get("core", {}) or {}
    if not core:
        st.info("MISSING · Artifact Core non disponibili.")
        return
    keys = ["mode", "core_observed_at", "loaded_at", "phase1_gate", "phase2_gate", "market_performance_computed"]
    st.dataframe(pd.DataFrame([{"Campo": k, "Stato": str(core[k])} for k in keys if k in core]), hide_index=True, width="stretch")
    for key, title in [("dataset", "Dati di mercato"), ("backtest", "Backtest"), ("demo", "Riconciliazione Demo"), ("tests", "Verifiche ingegneristiche")]:
        if key in core:
            with st.expander(title, expanded=True):
                st.json(core[key], expanded=True)
    if core.get("status") or core.get("reason"):
        st.info(f"{core.get('status', '')} · {core.get('reason', '')}")


def _quality(data: dict, filtered: pd.DataFrame) -> None:
    st.subheader("Qualità e provenienza")
    st.write("VALID: controlli di ricerca superati. DEGRADED: dato presente con limiti. MISSING: assente. SYNTHETIC: simulato ed escluso dal ranking.")
    st.caption("VALID nella dashboard non certifica dividendi, calendario, diritti d’uso o adeguatezza per un backtest nel Core. Data confidence descrive la copertura delle fonti, non la probabilità di un trade vincente.")
    _table(filtered, ["symbol", "name", "kind", "currency", "price_status", "volume_status", "ranking_eligible", "data_confidence", "observed_at", "available_at", "retrieved_at", "source", "source_url", "reason"], "quality_table")
    st.subheader("Ultimo aggiornamento")
    latest = data.get("latest_run")
    if isinstance(latest, dict):
        st.json(latest)
    elif latest:
        st.write(str(latest))
    else:
        st.info("Nessun run acquisito. Puoi consultare l’universo anche senza una fonte disponibile.")
    errors = data.get("errors", [])
    if errors:
        with st.expander("Fonti e controlli da verificare", expanded=True):
            for error in errors[:30]:
                st.write(error)
    st.download_button("Esporta la vista CSV", filtered.to_csv(index=False).encode("utf-8"), file_name="research_quality.csv", mime="text/csv")


def main() -> None:
    st.set_page_config(page_title="Trading Desk · Multi-Asset Intelligence", page_icon="◈", layout="wide")
    # One-time deep link: a direct phone URL opens Fineco without a sidebar.
    if st.query_params.get("fineco") == "1":
        st.session_state["workspace"] = "Fineco · Piano operativo"
        del st.query_params["fineco"]
    _styles()
    st.title("Opportunità multi-asset")
    st.caption("Ricerca e confronto · dati di fine seduta · Release " + APP_RELEASE)
    st.button(
        "Apri Fineco · Piano operativo", type="primary", key="fineco_primary_navigation",
        on_click=lambda: st.session_state.update({"workspace":"Fineco · Piano operativo"}),
    )
    with st.spinner("Lettura degli snapshot locali…"):
        try:
            data = _load(str(PROJECT_ROOT))
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"Snapshot non leggibile: {exc}")
            st.code("python -m src.intelligence.refresh --root .", language="bash")
            return
    if data.get('public_mode') and data.get('latest_run') is None:
        start_public_refresh(PROJECT_ROOT)
    _refresh_notice()
    metrics = _frame(data.get("metrics"))
    universe = _frame(data.get("universe"))
    latest_run = data.get("latest_run")
    errors=(latest_run or {}).get('errors',[])
    if errors:
        valid=int(metrics.get('price_status',pd.Series(dtype=str)).eq('VALID').sum())
        st.caption(f"Copertura incompleta: {valid}/{len(metrics)} prezzi validi. Alcune fonti non sono state aggiornate.")
        with st.expander('Stato delle fonti'):
            st.dataframe(pd.DataFrame(errors),hide_index=True,width='stretch')
        if not valid and public_status(PROJECT_ROOT).get('status')!='RUNNING':
            if st.button('Riprova caricamento',key='retry_sources'):
                start_public_refresh(PROJECT_ROOT,force=True)
                st.rerun()
    if isinstance(latest_run, dict) and latest_run.get("run_at"):
        st.caption(f"Ultimo run: {latest_run['run_at']} · fonti e date di disponibilità nella diagnostica e nell’Asset explorer.")
    if metrics.empty:
        metrics = universe.copy()
        for col in ["price_status", "volume_status"]:
            metrics[col] = "MISSING"
        metrics["ranking_eligible"] = False
    with st.sidebar:
        st.markdown("### Trading Desk")
        view = st.radio("Workspace", VIEWS, label_visibility="collapsed",key="workspace")
        st.divider()
        horizon = st.radio("Orizzonte di ricerca", list(HORIZONS), index=1)
        asset_classes = sorted(metrics.get("asset_class", pd.Series(dtype=str)).dropna().unique())
        selected_classes = st.multiselect("Asset class", asset_classes, default=asset_classes)
        regions = sorted(metrics.get("region", pd.Series(dtype=str)).dropna().unique())
        selected_regions = st.multiselect("Area geografica", regions, default=regions)
        query = st.text_input("Cerca simbolo o nome", placeholder="SPY, Europa, Treasury…")
        st.multiselect("Rischio volatilità",["Basso","Medio","Alto","Non determinabile"],default=["Basso","Medio","Alto","Non determinabile"],key="risk_filter")
        st.multiselect("Stato del segnale",["ENTRY CANDIDATE","RESEARCH CANDIDATE","WATCHLIST","BLOCKED"],default=["ENTRY CANDIDATE","RESEARCH CANDIDATE","WATCHLIST"],key="signal_filter")
        st.checkbox("Solo Early Opportunity",key="early_filter")
        only_valid = st.checkbox("Solo prezzi VALID", value=False)
        only_shortlist = st.checkbox("Solo shortlist", value=False)
        st.divider()
        if st.button("Aggiorna dati pubblici",width="stretch"):
            start_public_refresh(PROJECT_ROOT,force=True)
            st.rerun()
        if st.button("Rileggi snapshot", width="stretch"):
            _load.clear()
            st.rerun()
        with st.expander("Aggiorna le fonti"):
            st.caption("Da Terminale, nella cartella del progetto:")
            st.code("python -m src.intelligence.refresh --root .", language="bash")
            st.caption("La rilettura qui sopra non scarica nuovi dati.")
    filtered = metrics.copy()
    if "asset_class" in filtered:
        filtered = filtered[filtered["asset_class"].isin(selected_classes)]
    if "region" in filtered:
        filtered = filtered[filtered["region"].isin(selected_regions)]
    if query:
        matches = filtered.get("symbol", pd.Series("", index=filtered.index)).str.contains(query, case=False, regex=False, na=False)
        matches |= filtered.get("name", pd.Series("", index=filtered.index)).str.contains(query, case=False, regex=False, na=False)
        filtered = filtered[matches]
    if only_valid:
        filtered = filtered[filtered["price_status"].eq("VALID")]
    st.sidebar.caption("RESEARCH_ONLY · DEMO_READ_ONLY")
    store = Store(PROJECT_ROOT)
    if data.get('public_mode'):
        class SessionShortlist:
            def get_shortlist(self):return st.session_state.get('public_shortlist',[])
            def set_shortlist(self,symbols):
                if len(symbols)>10:raise ValueError('Massimo 10 strumenti')
                st.session_state['public_shortlist']=list(symbols)
        store=SessionShortlist()
    try:
        shortlist = store.get_shortlist()
    except (OSError, ValueError, sqlite3.DatabaseError):
        shortlist = []
    if only_shortlist:
        filtered = filtered[filtered["symbol"].isin(shortlist)]
    with st.sidebar.expander(f"Shortlist · {len(shortlist)}/10"):
        options = universe.get("symbol", pd.Series(dtype=str)).tolist()
        choice = st.multiselect("Monitoraggio approfondito", options, default=[s for s in shortlist if s in options], max_selections=10)
        if st.button("Salva shortlist", width="stretch"):
            try:
                store.set_shortlist(choice)
                st.success("Shortlist salvata.")
                st.rerun()
            except (OSError, ValueError, sqlite3.DatabaseError) as exc:
                st.error(str(exc))
    score, ret = HORIZONS[horizon]
    suffix = score.removeprefix("momentum_")
    # Delta must track the selected horizon; do not relabel the fixed 3m delta.
    filtered["score_change"] = filtered.get(f"score_change_{suffix}")
    ranked=_ranked(data,score)
    if not ranked.empty:
        added=[c for c in ranked.columns if c not in filtered.columns or c=='opportunity_score']
        filtered=filtered.drop(columns=['opportunity_score'],errors='ignore').merge(ranked[['symbol']+[c for c in added if c!='symbol']],on='symbol',how='left',validate='one_to_one')
    st.caption(f"{view} · {len(filtered)} strumenti nel filtro · {horizon}")
    if view == "Overview":
        _overview(data, filtered, score, ret)
    elif view == "Fineco · Piano operativo":
        fineco_workspace(data)
    elif view == "Asset explorer":
        _explorer(data, filtered)
    elif view == "Capital flows":
        _flows(filtered)
    elif view == "Macro & relative value":
        _macro(data, filtered)
    elif view == "Trading Desk monitor":
        _monitor(data)
    else:
        _quality(data, filtered)


if __name__ == "__main__":
    main()
