"""Interactive eToro REAL risk workspace. All account inputs are user-uploaded.

A public Streamlit app cannot access a ChatGPT plugin's OAuth connection.
No account, credentials or transactions are stored by the app or publisher.
"""
from __future__ import annotations

import json
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.intelligence.etoro_planner import analyze_etoro, parse_private_snapshot

DARK="#15283b"
TEAL="#087f7c"
MINT="#0cad98"
CORAL="#ef6b69"
AMBER="#c58a32"
LIGHT="#edf3f8"


def _read_private_upload():
    upload=st.file_uploader(
        "Carica snapshot privato eToro (JSON)",
        type=["json"],key="etoro_snapshot_upload",
        help="Generato dalla lettura eToro REALE in ChatGPT. Non inserire API key o password.",
    )
    if upload is None:
        return None
    try:
        raw=upload.getvalue()
        if len(raw)>350_000:
            raise ValueError("File troppo grande per la vista read-only")
        return parse_private_snapshot(json.loads(raw.decode("utf-8")))
    except (UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        st.error(f"Snapshot rifiutato: {error}")
        return None


def _stylized_signal(label, detail, status):
    color={
        "CRITICA":CORAL,"ALTA":CORAL,"MEDIA":AMBER,
        "OSSERVAZIONE":TEAL,
    }.get(status,TEAL)
    # Only static status tokens are injected. Dynamic details go through
    # safe Streamlit text rendering, not raw HTML.
    with st.container(border=True):
        st.markdown(
            '<div class="td-action-label" style="color:'+color+
            '">'+status+' · '+label+'</div>',unsafe_allow_html=True
        )
        st.write(detail)


def _allocation_chart(categories):
    rows=[(key,value) for key,value in categories.items() if value>0]
    if not rows:
        return go.Figure()
    colors={
        "Indici short / CFD":"#ee7771","Bond a leva":"#eda66c",
        "Obbligazionario":"#438eac","Oro e commodities":"#c6a25a",
        "Azionario / ETF":"#46ab9b","Altri asset":"#9998c9",
        "Liquidità":"#d3dce4",
    }
    fig=go.Figure(go.Pie(
        labels=[r[0] for r in rows],values=[r[1] for r in rows],
        hole=.66,sort=False,
        marker=dict(colors=[colors.get(r[0],DARK) for r in rows],
                    line=dict(width=2,color="#fff")),
        textinfo="percent",textposition="outside",
        hovertemplate="%{label}: %{value:,.2f} USD (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        height=355,margin=dict(l=5,r=5,t=15,b=10),
        paper_bgcolor="rgba(0,0,0,0)",font=dict(color=DARK),
        showlegend=True,legend=dict(orientation="h",y=-.12,x=0,font=dict(size=11)),
        annotations=[dict(text="Mark-to-market",font=dict(size=12,color=DARK),
                          showarrow=False,x=.5,y=.50)],
    )
    return fig


def _stress_chart(stress):
    labels=[f"S&P 500 +{s['shock_pct']}%" for s in stress]
    fig=go.Figure()
    fig.add_trace(go.Bar(
        name="Esposizione attuale",x=labels,
        y=[abs(x["current_pnl"]) for x in stress],
        marker_color=CORAL,text=[f"$ {abs(x['current_pnl']):,.0f}" for x in stress],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Dopo riduzione ipotizzata",x=labels,
        y=[abs(x["after_reduction_pnl"]) for x in stress],
        marker_color=TEAL,text=[f"$ {abs(x['after_reduction_pnl']):,.0f}" for x in stress],
        textposition="outside",
    ))
    ymax=max([abs(x["current_pnl"]) for x in stress]+[1])
    fig.update_layout(
        height=335,barmode="group",paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",font=dict(color=DARK),
        margin=dict(l=0,r=10,t=22,b=45),yaxis=dict(
            range=[0,ymax*1.2],title="Perdita aggiuntiva teorica (USD)",
            gridcolor="#edf0f4",zeroline=False,
        ),legend=dict(orientation="h",y=-.23,x=0),
    )
    fig.update_xaxes(showgrid=False)
    return fig


def etoro_workspace(data: dict) -> None:
    st.markdown(
        '<div class="td-section-kicker">BROKER WORKSPACE / RISK MANAGEMENT</div>',
        unsafe_allow_html=True,
    )
    st.subheader("eToro · Piano operativo")
    st.caption(
        "Portafoglio REALE · contenimento rischio, ribilanciamento e recupero "
        "disciplinato · **nessun nuovo versamento** · nessuna esecuzione automatica."
    )
    st.markdown(
        '<div class="td-risk-banner"><b>Principio operativo</b> — '
        'prima proteggere il capitale, poi valutare opportunità. '
        'Non aumentare la leva per recuperare perdite.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Come aggiornare il portafoglio eToro",expanded=True):
        st.write(
            "La connessione eToro collegata a ChatGPT non è trasferibile "
            "automaticamente a Streamlit Cloud. Esporta da ChatGPT uno snapshot "
            "del **conto REALE**, poi carica il file qui. "
            "Il file viene elaborato nella sessione e non viene salvato "
            "nel repository o nel feed di ricerca pubblico."
        )
        st.caption(
            "Il sito Streamlit rimane pubblico: carica soltanto un file con "
            "posizioni e importi, **mai credenziali o token**. "
            "La sessione del browser e il server gestiscono temporaneamente "
            "i dati durante l'analisi."
        )
    snapshot=_read_private_upload()
    if snapshot is None:
        st.info(
            "Nessun account caricato. L'analisi eToro non mostra valori di "
            "portafoglio finché non importi lo snapshot privato. "
            "Fineco e dashboard pubblica continuano a funzionare."
        )
        st.markdown("**Una volta importato troverai:**")
        cols=st.columns(3)
        for c,label,desc in zip(cols,
            ["Rischio netto e leva","Stress test SPX500","Lista azioni prioritarie"],
            ["Esposizioni e concentrazioni","Scenari +2%, +5%, +10%",
             "Ridurre, monitorare, attendere"]):
            with c:
                with st.container(border=True):
                    st.markdown("**"+label+"**")
                    st.caption(desc)
        return

    reduce=st.slider(
        "Simula una riduzione degli short SPX500 (%)",
        min_value=0,max_value=100,value=40,step=10,key="etoro_stress_reduction",
        help="Scenario matematico: non prepara né esegue alcuna chiusura.",
    )
    result=analyze_etoro(snapshot,reduction_pct=reduce)
    st.caption(
        "Fonte: eToro REALE (snapshot importato) · "+result["as_of"]+
        " · "+("DATI RECENTI" if result["fresh"] else "DATI OBSOLETI: aggiorna prima di agire")
    )
    if not result["fresh"]:
        st.warning(
            "Snapshot oltre 36 ore: i dati sottostanti potrebbero essere cambiati. "
            "Le priorità sotto sono soltanto una fotografia storica."
        )

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Equity USD",f"$ {result['equity']:,.0f}")
    c2.metric("Cash disponibile",f"$ {result['cash']:,.0f}")
    c3.metric("P/L aperto",f"$ {result['unrealized_pnl']:+,.0f}")
    c4.metric("Short SPX500",f"$ {result['short_notional']:,.0f}")
    c1,c2,c3=st.columns(3)
    c1.metric("Short / equity",f"{result['short_to_equity']*100:,.0f}%"
              if result["short_to_equity"] is not None else "—")
    c2.metric("Margine utilizzato",f"$ {result['used_margin']:,.0f}")
    c3.metric("Posizioni short SPX500",str(result["short_count"]))
    if result["short_to_equity"] is not None and result["short_to_equity"]>1:
        st.error(
            "Concentrazione critica: il nozionale short SPX500 supera il patrimonio. "
            "Le oscillazioni dell'indice possono incidere rapidamente sull'equity."
        )
    left,right=st.columns([1,1],gap="large")
    with left:
        st.markdown("#### Composizione del portafoglio")
        st.plotly_chart(_allocation_chart(result["category_values"]),
                        width="stretch",key="etoro_allocation_donut",
                        config={"displaylogo":False})
        st.caption(
            "Valori correnti delle posizioni, non nozionali leveraged. "
            "Le allocazioni mark-to-market non misurano da sole il rischio."
        )
    with right:
        st.markdown("#### Shock avversi agli short")
        st.plotly_chart(_stress_chart(result["stress"]),
                        width="stretch",key="etoro_short_stress",
                        config={"displaylogo":False})
        st.caption(
            "Effetto lineare sui soli short SPX500, a tassi invariati. "
            "Esclude gap, costi overnight, altre posizioni e margin call."
        )

    st.markdown("### Azioni da valutare, in ordine di priorità")
    for action in result["actions"]:
        with st.container(border=True):
            grade = action["severity"]
            color = {
                "CRITICA":"#e36b64","ALTA":"#e69b55",
                "MEDIA":"#b3892d","OSSERVAZIONE":"#087f7c",
            }.get(grade,"#087f7c")
            st.markdown(
                '<span style="display:inline-block;border-radius:999px;'
                'padding:4px 10px;margin:0 0 6px;font-size:.72rem;'
                'font-weight:800;letter-spacing:.07em;background:'
                + color + '18;color:' + color + '">'
                + grade + '</span>',unsafe_allow_html=True
            )
            st.markdown(
                f"**{action['priority']:02d}. {action['instrument']} — {action['verb']}**"
            )
            st.caption(action["reason"])
            st.write(action["checkpoint"])
    st.markdown("### Esposizioni e posizioni")
    overview=pd.DataFrame(result["holdings"])
    if not overview.empty:
        shown=overview.rename(columns={
            "symbol":"Strumento","value":"Valore USD",
            "exposure":"Esposizione USD","pnl":"P/L USD",
            "leverage":"Leva media","position_count":"Posizioni",
            "category":"Categoria",
        })
        st.dataframe(
            shown[["Strumento","Categoria","Valore USD","Esposizione USD",
                   "P/L USD","Leva media","Posizioni"]],
            width="stretch",hide_index=True,
            column_config={
                "Valore USD":st.column_config.NumberColumn(format="$ %.2f"),
                "Esposizione USD":st.column_config.NumberColumn(format="$ %.2f"),
                "P/L USD":st.column_config.NumberColumn(format="$ %+.2f"),
                "Leva media":st.column_config.NumberColumn(format="%.1f x"),
            },
        )
    with st.expander("Dettaglio stop delle posizioni short SPX500"):
        positions=result["spx_positions"]
        if not positions:
            st.caption("Nessun dettaglio posizione short incluso nel file.")
        else:
            data_frame=pd.DataFrame(positions)
            st.dataframe(
                data_frame.rename(columns={
                    "position_id":"Position ID","units":"Unità",
                    "current_rate":"Prezzo attuale",
                    "stop_loss":"Stop loss","pnl":"P/L aperto USD",
                    "leverage":"Leva",
                })[["Position ID","Unità","Prezzo attuale",
                    "Stop loss","P/L aperto USD","Leva"]],
                hide_index=True,width="stretch",
            )
            st.caption(
                "Stop loss indicativi dal broker. Non garantiscono "
                "esecuzioni al prezzo previsto, specialmente sui gap."
            )
    st.caption(
        "Ordini pendenti nello snapshot: "+str(result["pending_orders_count"])+
        " · Nessun ordine può essere inviato da questa dashboard."
    )
    with st.expander("Metodologia e limiti"):
        for item in result["limitations"]:
            st.write("• "+item)
        st.write(
            "I segnali multi-asset della dashboard possono contestualizzare "
            "SPY, obbligazioni e oro, ma non modificano retroattivamente "
            "il rischio delle posizioni né autorizzano trade."
        )
