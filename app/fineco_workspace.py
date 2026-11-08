"""Session-private Fineco decision panel: no holdings in public code or exports."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen
import pandas as pd
import streamlit as st

from src.intelligence.fineco_planner import (
    FINECO_POSITIONS, build_fineco_plan, dashboard_from_public_brief,
)

PUBLIC_DATA_URL = (
    "https://raw.githubusercontent.com/simfed78/"
    "Market-Intelligence-Operations-Console/research-data/"
    "exports/research/latest.json"
)


@st.cache_data(ttl=1800, show_spinner=False)
def _published_research():
    """Read only the public, derived GitHub brief; never write account data."""
    try:
        req = Request(PUBLIC_DATA_URL, headers={"User-Agent":"MarketIntelligenceFinecoReadOnly/1.0"})
        with urlopen(req, timeout=8) as response:
            raw = response.read(1_500_001)
        if len(raw) > 1_500_000:
            return None
        return dashboard_from_public_brief(json.loads(raw.decode("utf-8")))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return None


def _signal_text(signal):
    details = signal.get("proxies", [])
    if not details:
        return signal["state"] + " · nessuna fonte idonea"
    return signal["state"] + " · " + ", ".join(
        f"{p['symbol']} {p['technical_score']:.0f}/100 ({p['status']})"
        for p in details
    )


def fineco_workspace(data: dict) -> None:
    st.subheader("Fineco · Azioni da valutare")
    st.caption(
        "Portafoglio buy & hold tattico · orizzonte 12 mesi · massimo 8 strumenti in questa "
        "sezione, solo 3 candidati a nuovi acquisti. Nessun ordine automatico."
    )
    st.info(
        "Il budget previsto è **1.000 € al mese**, disponibile soltanto dopo l'accredito "
        "dello stipendio. Non è necessario investire tutto subito; ciò che non si investe "
        "resta liquidità. Non utilizziamo capitale o posizioni eToro."
    )
    with st.container(border=True):
        st.markdown("**1. Qual è il budget realmente investibile?**")
        budget = st.number_input(
            "Liquidità Fineco già disponibile da destinare agli investimenti (€)",
            min_value=0.0, value=0.0, step=50.0, key="fineco_actual_cash",
            help="Non inserire lo stipendio finché non è effettivamente accreditato.",
        )
        confirmed_cash = st.checkbox(
            "Confermo che questa liquidità è già presente e disponibile su Fineco",
            value=False, key="fineco_cash_confirmed",
        )
    with st.expander("2. Inserisci gli attuali controvalori Fineco (solo questa sessione)", expanded=False):
        st.caption(
            "Nessun collegamento al broker. Valori iniziali volutamente vuoti: "
            "i tuoi saldi NON sono memorizzati su GitHub o condivisi con altri visitatori. "
            "I dati inseriti potrebbero sparire quando si riavvia il browser/app."
        )
        holdings = {}
        for p in FINECO_POSITIONS:
            holdings[p["code"]] = st.number_input(
                f"{p['code']} · {p['name']} (€)",
                min_value=0.0, value=0.0, step=25.0,
                key=f"fineco_value_{p['code']}",
            )
        holdings_confirmed = st.checkbox(
            "Confermo di aver aggiornato TUTTI i controvalori (inclusi gli zeri reali)",
            value=False, key="fineco_holdings_confirmed",
        )
    published = _published_research()
    research = published if published is not None else data
    st.caption(
        "Segnali: " + ("snapshot GitHub qualificato" if published is not None
                      else "snapshot del server Streamlit (se disponibile)")
        + " · nessun prezzo Fineco stimato dai proxy USA."
    )
    plan = build_fineco_plan(
        research, available_cash_eur=budget, cash_confirmed=confirmed_cash,
        holdings=holdings, holdings_confirmed=holdings_confirmed,
    )
    quality = plan["quality"]
    with st.container(border=True):
        st.markdown("**3. Proposta operativa della settimana**")
        if quality["fresh"]:
            st.caption(
                f"Ultimo run completo: {quality['as_of']} · "
                f"prezzi VALID {quality['valid_coverage']:.1%} · "
                f"macro: {quality['macro_status']}."
            )
        else:
            st.error(
                "Dati della dashboard mancanti, obsoleti o insufficienti. "
                "Nessuna proposta d'acquisto viene abilitata."
            )
        if quality["macro_status"] in ("MISSING", "DEGRADED"):
            st.caption(
                "Dati macro della dashboard non qualificati: le proposte riflettono "
                "solo regole di portafoglio e ricerca tecnica, non una previsione macro."
            )
        if not confirmed_cash or budget == 0:
            st.warning("Budget investibile non confermato: **0 € di acquisti suggeriti ora**.")
        elif not holdings_confirmed:
            st.warning(
                "Aggiorna e conferma i controvalori Fineco: senza il portafoglio "
                "corrente non possiamo determinare il rischio di concentrazione."
            )
        c1,c2,c3 = st.columns(3)
        c1.metric("Liquidità dichiarata", f"{plan['available_cash_eur']:,.0f} €")
        c2.metric("Acquisti da valutare", f"{plan['suggested_eur']:,.0f} €")
        c3.metric("Da conservare cash", f"{plan['kept_cash_eur']:,.0f} €")
        actions = pd.DataFrame(plan["rows"])
        shown = actions[["code","name","isin","wrapper","signal","action","proposed_eur","reason"]].rename(columns={
            "code":"ETF/ETC","name":"Strumento","isin":"ISIN","wrapper":"Tipo",
            "signal":"Stato segnale","action":"Azione","proposed_eur":"EUR massimo","reason":"Motivazione",
        })
        st.dataframe(
            shown, hide_index=True, width="stretch",
            column_config={
                "EUR massimo":st.column_config.NumberColumn(
                    "EUR massimo", format="%.0f €"
                ),
                "ISIN":st.column_config.TextColumn("ISIN"),
            },
        )
        st.caption(
            "Somme indicative prima dei costi, non quantità eseguibili. Fineco acquista "
            "quote intere: verificare sempre prezzo/valuta di quotazione, commissioni "
            "ordinarie o Replay, spread, KID e idoneità prima di ogni operazione."
        )
        if plan["plan_ready"]:
            st.download_button(
                "Esporta proposta CSV (non è un ordine)",
                data=shown.to_csv(index=False).encode("utf-8"),
                file_name="fineco_azioni_proposte.csv",
                mime="text/csv",
                key="fineco_export_actions",
            )
    with st.expander("4. Perché queste tre scelte? Traduzione dei segnali multi-asset"):
        st.markdown("**VALL · azionario globale**")
        st.write(
            "Esaminiamo VT e ACWI, proxy USA di mercato globale. "
            "I settoriali XLV, XLP e IBB possono indicare rotazione difensiva, "
            "ma NON diventano nuovi ETF del portafoglio."
        )
        st.caption(
            "12 mesi: " + _signal_text(plan["signals"]["world_12m"])
            + " · 3 mesi: " + _signal_text(plan["signals"]["world_3m"])
        )
        st.markdown("**PRAB · governativi euro 0–1 anno**")
        st.write(
            "È il comparto difensivo già presente. BIL, SHY e BKLN sono strumenti "
            "statunitensi: i loro tassi, duration, rischio di credito e cambio NON "
            "sono equivalenti a PRAB. L'allocazione deriva da una regola di rischio, "
            "non da un falso segnale di acquisto PRAB."
        )
        st.markdown("**SGLN · ETC su oro fisico**")
        st.write(
            "GLD e IAU sono proxy del trend dell'oro. Il segnale è orientativo, "
            "senza copertura EUR/USD e senza garanzia che segua il prezzo dell'ETC "
            "in euro nello stesso modo. Le aziende minerarie già possedute NON "
            "costituiscono un'esposizione diretta all'oro."
        )
        st.caption("3 mesi: " + _signal_text(plan["signals"]["gold_3m"]))
        st.markdown("**Commodities, energia e rotazione settoriale**")
        st.write(
            "USO/DBC e XLV/XLP alimentano solo il contesto tattico: "
            "non acquistiamo automaticamente USO, XLV, XLP o altri ETF settoriali "
            "quotati negli Stati Uniti. Nessuna lista dispersiva."
        )
        st.caption(
            "Commodities: " + _signal_text(plan["signals"]["commodities_3m"])
            + " · difensivi: " + _signal_text(plan["signals"]["defensives_3m"])
        )
        st.write(
            "L'Opportunity Score è un percentile entro asset class: non "
            "misura il rendimento futuro né autorizza un ingresso. "
            "Macro MISSING non viene sostituito con una previsione."
        )
    with st.expander("5. Posizioni che non aumenterei automaticamente"):
        legacy = [p for p in FINECO_POSITIONS if not p["buy"]]
        st.dataframe(pd.DataFrame([{
            "ETF / gruppo":p["name"],"Ruolo":p["role"],"Azione":"MANTENERE / RIVEDERE COSTI",
        } for p in legacy]),hide_index=True,width="stretch")
        st.caption(
            "Le posizioni in portafoglio non vengono vendute per seguire un ranking "
            "settimanale: ogni eventuale vendita richiede una valutazione indipendente "
            "di plusvalenze, costi e rischi."
        )
    st.caption(
        "RESEARCH_ONLY · nessun accesso al conto Fineco eToro · i dati personali "
        "inseriti restano nella sessione Streamlit, non negli export pubblici."
    )
