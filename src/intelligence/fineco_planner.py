"""Fineco buy-and-hold decision support: a small, fixed European product set.

No broker integrations, execution, account data, investment return forecasts
or fabricated translations of U.S. ETF prices into European ETF quotes.

A dashboard signal is a qualitative RESEARCH overlay; it can accelerate or
delay a monthly tranche, but never creates a validated ENTRY/BUT signal.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import pandas as pd

# Existing legacy instruments have purposely no guessed ISIN. The buy set
# is exactly three instruments. This is a *planning* registry, not a broker
# eligibility or listing verification feed.
FINECO_POSITIONS = (
    dict(code="VALL", name="Vanguard FTSE Global All-Cap", isin="IE000VAHT5T0", wrapper="UCITS ETF", role="Azionario globale", buy=True),
    dict(code="PRAB", name="Amundi Prime Euro Government 0-1Y", isin="LU2233156582", wrapper="UCITS ETF", role="Gov. EUR breve", buy=True),
    dict(code="SGLN", name="iShares Physical Gold", isin="IE00B4ND3602", wrapper="ETC (non UCITS)", role="Oro fisico", buy=True),
    dict(code="EUR_GOV", name="iShares Core EUR Government Bond", isin="", wrapper="UCITS ETF", role="Gov. EUR duration medio-alta", buy=False),
    dict(code="LIFESTRATEGY60", name="Vanguard LifeStrategy 60% Equity", isin="", wrapper="UCITS ETF", role="Multi-asset 60/40", buy=False),
    dict(code="UST01", name="Vanguard US Treasury 0-1Y", isin="", wrapper="UCITS ETF", role="Treasury USD, rischio FX", buy=False),
    dict(code="METALS", name="iShares Essential Metals Producers", isin="", wrapper="UCITS ETF", role="Azioni minerarie, NON oro fisico", buy=False),
    dict(code="ROBOTICS", name="KraneShares Humanoid Robotics & AI", isin="", wrapper="UCITS ETF", role="Azioni tematiche", buy=False),
)
BUY_SET = ("VALL", "PRAB", "SGLN")
FINECO_CODES = frozenset(p["code"] for p in FINECO_POSITIONS)
# No new sector ETF. At most 8 lines here, including the 7 already known.
MAX_SNAPSHOT_AGE_HOURS = 72
MIN_ECONOMIC_TRANCHE_EUR = 150


def _dt(value):
    if isinstance(value, datetime):
        time = value
    else:
        time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if time.tzinfo is None:
        raise ValueError("UTC/fuso orario mancante")
    return time.astimezone(timezone.utc)


def _valid_amount(value):
    if isinstance(value, bool):
        raise ValueError("Budget non numerico")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Budget o posizione non finiti/non validi")
    return value


def _validated_signal(rows, symbols):
    """Inspect full completed-universe rankings, not only the Top 10."""
    if rows is None or getattr(rows, "empty", True):
        return dict(state="MISSING", proxies=[], reason="Nessun ranking disponibile")
    sample = rows[rows.symbol.isin(symbols)]
    details = []
    for r in sample.to_dict("records"):
        valid = (
            r.get("price_status") == "VALID"
            and r.get("signal_state") in ("RESEARCH CANDIDATE", "WATCHLIST")
            and r.get("model_version") == "technical-priority-v1"
            and r.get("technical_score") is not None
        )
        if not valid:
            continue
        try:
            score = float(r["technical_score"])
            timing = float(r["timing_score"])
        except (ValueError, TypeError, KeyError):
            continue
        if not all(math.isfinite(x) for x in (score, timing)):
            continue
        details.append(dict(
            symbol=r["symbol"], technical_score=round(score, 1),
            timing=timing, status=r["signal_state"],
            observation=str(r.get("observed_at") or ""),
        ))
    if not details:
        return dict(state="MISSING", proxies=[], reason="Proxy non validi: nessuna inferenza")
    strong = [p for p in details if
              p["status"] == "RESEARCH CANDIDATE"
              and p["technical_score"] >= 60 and p["timing"] >= 50]
    if len(strong) == len(details) and len(details) >= 2:
        state = "FAVOREVOLE"
    elif strong:
        state = "MISTO"
    else:
        state = "DEBOLE"
    return dict(
        state=state, proxies=details,
        reason=f"{len(strong)}/{len(details)} proxy con trend tecnico favorevole",
    )


PUBLIC_PROXIES = frozenset(("VT", "ACWI", "GLD", "IAU", "USO", "DBC", "XLV", "XLP"))

def dashboard_from_public_brief(brief, *, now=None):
    """Validate and translate the versioned GitHub research snapshot; no broker data."""
    now = _dt(now or datetime.now(timezone.utc))
    if not isinstance(brief, dict) or any((
        brief.get("schema_version") != "research-brief.v1",
        brief.get("mode") != "RESEARCH_ONLY",
        brief.get("publication_status") != "QUALIFIED_RESEARCH",
        brief.get("model_version") != "technical-priority-v1",
    )):
        raise ValueError("Contratto di ricerca non valido")
    generated = _dt(brief["generated_at"])
    completed = _dt(brief["completed_run_at"])
    if (generated < completed or generated > now or completed > now
            or (now-generated).total_seconds() > MAX_SNAPSHOT_AGE_HOURS * 3600
            or (now-completed).total_seconds() > MAX_SNAPSHOT_AGE_HOURS * 3600):
        raise ValueError("Snapshot obsoleto, futuro o temporalmente incoerente")
    quality = brief.get("quality") or {}
    ratio = float(quality.get("valid_ratio", 0))
    if not math.isfinite(ratio) or ratio < .70 or ratio > 1:
        raise ValueError("Copertura prezzi insufficiente")
    opportunities = {}
    for horizon in ("3m", "12m"):
        raw = ((brief.get("horizons") or {}).get(horizon) or {}).get("fineco_proxies")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Proxy Fineco mancanti dalla pubblicazione")
        rows = []
        for item in raw:
            if not isinstance(item, dict) or item.get("symbol") not in PUBLIC_PROXIES:
                raise ValueError("Simbolo non ammesso")
            rows.append({k:item.get(k) for k in (
                "symbol","price_status","signal_state","model_version",
                "technical_score","timing_score","observed_at",
            )})
        if len({r["symbol"] for r in rows}) != len(rows):
            raise ValueError("Proxy duplicati")
        opportunities[horizon] = pd.DataFrame(rows)
    return {
        "latest_run":{"run_at":completed.isoformat()},
        "quality":{"valid_ratio":ratio},
        "opportunities":opportunities,
        "macro":{"status":str(quality.get("macro_status") or "MISSING")},
        "source_kind":"qualified-public-export",
    }

def build_fineco_plan(
    dashboard, *,
    available_cash_eur=0,
    cash_confirmed=False,
    holdings=None,
    holdings_confirmed=False,
    now=None,
):
    """Pure, deterministic portfolio-aware indicative actions.

    Account value is always caller supplied. No available cash -> zero buy.
    Missing/stale completed public run -> zero buy. Even otherwise outputs
    remain non-executable research suggestions until manual price/fee checks.
    """
    now = _dt(now or datetime.now(timezone.utc))
    cash = _valid_amount(available_cash_eur)
    holdings = dict(holdings or {})
    if any(k not in FINECO_CODES for k in holdings):
        raise ValueError("Strumento fuori universo Fineco")
    values = {p["code"]: _valid_amount(holdings.get(p["code"], 0)) for p in FINECO_POSITIONS}
    current_total = sum(values.values())
    if not holdings_confirmed:
        current_total = None

    latest = dashboard.get("latest_run") if isinstance(dashboard, dict) else None
    age = None
    if isinstance(latest, dict) and latest.get("run_at"):
        try:
            age = (now - _dt(latest["run_at"])).total_seconds() / 3600
        except (TypeError, ValueError):
            age = None
    metrics = dashboard.get("metrics") if isinstance(dashboard, dict) else None
    has_metrics = metrics is not None and len(metrics) and "price_status" in metrics
    coverage = float(metrics.price_status.eq("VALID").mean()) if has_metrics else 0.0
    if dashboard.get("source_kind") == "qualified-public-export":
        coverage = float((dashboard.get("quality") or {}).get("valid_ratio", 0))
    valid_coverage = math.isfinite(coverage) and .70 <= coverage <= 1
    fresh = age is not None and 0 <= age <= MAX_SNAPSHOT_AGE_HOURS and bool(valid_coverage)

    ranked = dashboard.get("opportunities", {}) if fresh else {}
    equity = _validated_signal(ranked.get("12m"), ("VT", "ACWI"))
    equity_medium = _validated_signal(ranked.get("3m"), ("VT", "ACWI"))
    gold = _validated_signal(ranked.get("3m"), ("GLD", "IAU"))
    energy = _validated_signal(ranked.get("3m"), ("USO", "DBC"))
    defensive = _validated_signal(ranked.get("3m"), ("XLV", "XLP"))
    quality = dict(fresh=fresh, age_hours=round(age, 2) if age is not None else None,
                   valid_coverage=round(coverage, 3),
                   as_of=latest.get("run_at") if isinstance(latest, dict) else None,
                   macro_status=(dashboard.get("macro") or {}).get("status", "MISSING")
                   if isinstance(dashboard, dict) else "MISSING")

    # Core allocation is a policy starting point, NOT fit/expected return
    # calibrated by the dashboard's percentile score.
    if equity["state"] == "FAVOREVOLE" and equity_medium["state"] in ("FAVOREVOLE", "MISTO"):
        global_fraction = .45
        equity_reason = "Broad world proxy favorevole su 12m e non debole su 3m"
    elif equity["state"] in ("FAVOREVOLE", "MISTO", "DEBOLE"):
        global_fraction = .20
        equity_reason = "Tranche prudente: conferma globale parziale o debole"
    else:
        global_fraction = 0
        equity_reason = "Proxy globale non disponibile: non promuovere un ingresso"
    gold_fraction = .10 if gold["state"] == "FAVOREVOLE" else 0
    # PRAB has NO valid EUR government duration-0-1y proxy: this is a
    # structural defensive allocation, NOT a signal from USD BIL/SHY.
    base_fractions = {"VALL": global_fraction, "PRAB": .35, "SGLN": gold_fraction}

    # Treat this as an indicative capital allocation, not a broker order.
    if not cash_confirmed or not fresh or not holdings_confirmed:
        allocatable = 0.0
    else:
        allocatable = cash

    total_after = current_total + allocatable if current_total is not None else None
    equity_current = (
        values["VALL"] + .60 * values["LIFESTRATEGY60"]
        + values["METALS"] + values["ROBOTICS"]
    )
    constraints = {}
    if total_after and allocatable > 0:
        # A cap includes existing multi-asset exposure; no forced selling.
        if equity_current / total_after > .45:
            base_fractions["VALL"] = 0
            constraints["VALL"] = "Azionario effettivo già oltre 45% del portafoglio"
        if values["PRAB"] / total_after > .40:
            base_fractions["PRAB"] = 0
            constraints["PRAB"] = "Gov. EUR breve già oltre 40% del portafoglio"
        if values["SGLN"] / total_after >= .10:
            base_fractions["SGLN"] = 0
            constraints["SGLN"] = "Oro fisico già al limite del 10%"
    amounts = {}
    for code, fraction in base_fractions.items():
        gross = math.floor((allocatable * fraction + 1e-9) / 10) * 10
        amounts[code] = gross if gross >= MIN_ECONOMIC_TRANCHE_EUR else 0.0
    held_cash = round(allocatable - sum(amounts.values()), 2)
    if held_cash < -1e-7:
        raise AssertionError("Le proposte non possono superare il budget")
    rows = []
    by_code = {p["code"]: p for p in FINECO_POSITIONS}
    for code in BUY_SET:
        p = by_code[code]
        signal = {"VALL": equity, "PRAB": None, "SGLN": gold}[code]
        a = amounts[code]
        if not fresh:
            action, why = "ATTENDERE", "Dati di mercato mancanti/obsoleti"
        elif not cash_confirmed or cash <= 0:
            action, why = "ATTENDERE", "Budget non ancora confermato/disponibile"
        elif not holdings_confirmed:
            action, why = "ATTENDERE", "Valori Fineco non aggiornati: nessuna proposta eseguibile"
        elif a > 0:
            action = "VALUTARE ACQUISTO"
            why = (equity_reason if code == "VALL" else
                   "Allocazione difensiva in EUR (non derivata dal proxy USA)" if code == "PRAB" else
                   "Oro forte nei proxy USA: verificare differenze di cambio e prodotto ETC")
        else:
            action = "ACCUMULARE LIQUIDITÀ"
            why = constraints.get(code) or (
                "Segnale oro non abbastanza forte o lotto troppo piccolo" if code == "SGLN" else
                "Tranche sotto soglia economica/nessuna conferma tecnica")
        rows.append(dict(
            code=code, name=p["name"], isin=p["isin"], wrapper=p["wrapper"],
            action=action, proposed_eur=a, signal=signal["state"] if signal else "NESSUN PROXY EUR",
            reason=why, needs_manual_check="Prezzo/quote intere, commissioni Fineco, spread, negoziabilità e KID",
        ))

    return dict(
        quality=quality, available_cash_eur=round(cash, 2),
        cash_confirmed=bool(cash_confirmed), holdings_confirmed=bool(holdings_confirmed),
        current_total_eur=round(current_total, 2) if current_total is not None else None,
        plan_ready=bool(fresh and cash_confirmed and holdings_confirmed and cash > 0),
        suggested_eur=round(sum(amounts.values()), 2),
        kept_cash_eur=held_cash,
        rows=rows,
        signals=dict(world_12m=equity, world_3m=equity_medium, gold_3m=gold,
                     commodities_3m=energy, defensives_3m=defensive),
        policy="Portafoglio ridotto: nuovi acquisti solo VALL, PRAB, SGLN; non acquistare settoriali USA.",
        note="Importi massimi indicativi, non ordini. Il ranking tecnico non valida ENTRY e non predice i rendimenti futuri.",
    )
