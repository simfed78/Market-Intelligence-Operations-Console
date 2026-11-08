"""Pure, conservative eToro REAL risk research from a user-supplied snapshot.

IMPORTANT: this module has NO eToro API client, orders, authenticated tokens,
shared persistent storage, market execution, or access to Fineco holdings.
The snapshot can be exported privately through the ChatGPT eToro connector
and deliberately imported by the owner into their Streamlit session.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

SCHEMA_VERSION = "etoro-private-snapshot.v1"
MAX_POSITIONS = 500
MAX_HOLDINGS = 100
RISK_FRESHNESS_HOURS = 36

BONDS = frozenset({"BOND", "DTLA.L", "EUNA.DE", "IB01.L", "PRAB.DE"})
LEVERAGED_BONDS = frozenset({"TMF"})
COMMODITIES = frozenset({"GLD", "GOLD", "SILVER", "SLV", "IAU"})
SPX_SYMBOLS = frozenset({"SPX500"})
EQUITY_ETFS = frozenset({"SPY", "EXUS.DE", "KWEB", "FLXI.L", "FLXC.L",
                         "FLXB.L", "MWOD.DE"})


def _finite(x, *, nonnegative=False):
    if isinstance(x, bool):
        raise ValueError("Valore non numerico")
    try:
        f = float(x)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Numero mancante o non valido") from None
    if not math.isfinite(f) or (nonnegative and f < 0):
        raise ValueError("Numero negativo o non finito")
    return f


def _utc(s):
    try:
        date = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError
        return date.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Timestamp obbligatorio con fuso orario") from None


def _category(symbol):
    if symbol in SPX_SYMBOLS:
        return "Indici short / CFD"
    if symbol in LEVERAGED_BONDS:
        return "Bond a leva"
    if symbol in BONDS:
        return "Obbligazionario"
    if symbol in COMMODITIES:
        return "Oro e commodities"
    if symbol in EQUITY_ETFS:
        return "Azionario / ETF"
    return "Altri asset"


def parse_private_snapshot(payload, *, now=None):
    """Strict public upload contract; return a safe normalized copy.

    Never persist the payload in GitHub, SQLite, Streamlit cache or logs.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Formato non riconosciuto: richiesto " + SCHEMA_VERSION)
    if payload.get("account") != "real" or payload.get("currency") != "USD":
        raise ValueError("Solo conto REALE in USD: non mescolare Demo e valute")
    instant = _utc(payload.get("as_of"))
    now = _utc(now or datetime.now(timezone.utc))
    if instant > now.replace(microsecond=0) and (instant-now).total_seconds() > 300:
        raise ValueError("Snapshot con data futura")
    freshness = max(0, (now-instant).total_seconds()/3600)
    raw_totals = payload.get("totals")
    if not isinstance(raw_totals, dict):
        raise ValueError("Totali del conto mancanti")
    totals = {
        "equity":_finite(raw_totals.get("equity"),nonnegative=True),
        "available_cash":_finite(raw_totals.get("available_cash"),nonnegative=True),
        "used_margin":_finite(raw_totals.get("used_margin"),nonnegative=True),
        "unrealized_pnl":_finite(raw_totals.get("unrealized_pnl")),
    }
    holdings = payload.get("holdings")
    if not isinstance(holdings, list) or not holdings or len(holdings)>MAX_HOLDINGS:
        raise ValueError("Holdings mancanti o oltre il limite")
    clean_holdings = []
    for record in holdings:
        if not isinstance(record, dict):
            raise ValueError("Holding non valido")
        symbol = record.get("symbol")
        if not isinstance(symbol, str) or not (1 <= len(symbol) <= 30):
            raise ValueError("Simbolo non valido")
        if any(h["symbol"]==symbol for h in clean_holdings):
            raise ValueError("Symbol duplicato nella sintesi")
        val = _finite(record.get("value"),nonnegative=True)
        exp = _finite(record.get("exposure"))
        pnl = _finite(record.get("pnl"))
        leverage = _finite(record.get("leverage"),nonnegative=True)
        n = record.get("position_count",0)
        if not isinstance(n,int) or isinstance(n,bool) or not (0<=n<=MAX_POSITIONS):
            raise ValueError("Numero posizioni non valido")
        clean_holdings.append({
            "symbol":symbol, "value":val, "exposure":exp, "pnl":pnl,
            "leverage":leverage, "position_count":n,
            "category":_category(symbol),
        })
    positions = payload.get("positions",[])
    if not isinstance(positions,list) or len(positions)>MAX_POSITIONS:
        raise ValueError("Posizioni di dettaglio non valide")
    clean_positions = []
    ids = set()
    for record in positions:
        if not isinstance(record,dict):
            raise ValueError("Posizione non valida")
        symbol = record.get("symbol")
        if symbol not in SPX_SYMBOLS:  # import only what stress-testing uses
            continue
        pid=record.get("position_id")
        if not isinstance(pid,int) or isinstance(pid,bool) or pid in ids or pid<=0:
            raise ValueError("ID posizione errato o duplicato")
        ids.add(pid)
        if record.get("direction")!="short":
            raise ValueError("Direzione SPX500 incompatibile con il dettaglio short")
        units=_finite(record.get("units"),nonnegative=True)
        rate=_finite(record.get("current_rate"),nonnegative=True)
        if units<=0 or rate<=0:
            raise ValueError("Units e rate devono essere positivi")
        lev=_finite(record.get("leverage"),nonnegative=True)
        clean_positions.append({
            "position_id":pid,"symbol":symbol,"direction":"short",
            "units":units,"current_rate":rate,"leverage":lev,
            "pnl":_finite(record.get("pnl")),
            "stop_loss":_finite(record.get("stop_loss"),nonnegative=True)
                         if record.get("stop_loss") is not None else None,
        })
    pending=payload.get("pending_orders_count",0)
    if not isinstance(pending,int) or isinstance(pending,bool) or pending<0:
        raise ValueError("Ordini pendenti non validi")
    # Fails closed on a missing or conflicting SPX details; never use a
    # fabricated units*rate approximation when that disagrees with the API.
    spx_rows = [p for p in clean_holdings if p["symbol"]=="SPX500"]
    if spx_rows and spx_rows[0]["exposure"] < -0.01 and clean_positions:
        notional = sum(p["units"]*p["current_rate"] for p in clean_positions)
        reported = abs(spx_rows[0]["exposure"])
        if abs(notional-reported)>max(30,reported*.02):
            raise ValueError("Nozionale SPX500 non riconciliato con le posizioni")
    return {
        "schema_version":SCHEMA_VERSION,"as_of":instant.isoformat(),
        "age_hours":round(freshness,2),
        "fresh":freshness<=RISK_FRESHNESS_HOURS,
        "account":"real","currency":"USD","totals":totals,
        "holdings":clean_holdings,"positions":clean_positions,
        "pending_orders_count":pending,
    }


def analyze_etoro(snapshot, *, reduction_pct=0):
    """Compute actionable *research priorities* and explicit risk scenarios."""
    if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=SCHEMA_VERSION:
        raise ValueError("Snapshot non validato")
    reduction=_finite(reduction_pct,nonnegative=True)
    if reduction>100:
        raise ValueError("Riduzione fuori range")
    totals=snapshot["totals"]
    equity=totals["equity"]
    holdings=snapshot["holdings"]
    spx=[h for h in holdings if h["symbol"]=="SPX500"]
    short_notional=sum(abs(h["exposure"]) for h in spx if h["exposure"]<0)
    if not spx and snapshot["positions"]:
        raise ValueError("Sintesi SPX500 mancante")
    short_count=sum(h["position_count"] for h in spx)
    stress=[
        {
            "shock_pct":pct,
            "current_pnl":round(-short_notional*pct/100,2),
            "after_reduction_pnl":round(-short_notional*(1-reduction/100)*pct/100,2),
            "equity_fraction":round(-short_notional*pct/100/equity,4)
                               if equity>0 else None,
        }
        for pct in (2,5,10)
    ]
    category_values={}
    for h in holdings:
        category_values[h["category"]]=category_values.get(h["category"],0)+h["value"]
    category_values["Liquidità"]=totals["available_cash"]
    # An index notional is a risk exposure, not the mark-to-market holding value.
    # Current holdings are grouped using their marked current values only.
    risk_ratio=short_notional/equity if equity>0 else None
    used_margin_ratio=totals["used_margin"]/equity if equity>0 else None
    close_symbols=[]
    actions=[]
    if short_notional>0:
        actions.append({
            "priority":1, "severity":"CRITICA" if risk_ratio is None or risk_ratio>=1 else "ALTA",
            "instrument":"SPX500 · short x20", "verb":"VALUTARE RIDUZIONE",
            "reason":"Esposizione ribassista concentrata; rischio di ulteriori perdite e costi overnight.",
            "checkpoint":"Verificare ogni posizione, spread, stop e margine sul broker.",
        })
    if any(h["symbol"]=="TMF" for h in holdings):
        actions.append({
            "priority":2,"severity":"ALTA","instrument":"TMF · Treasury 3x",
            "verb":"RIVEDERE / RIDURRE",
            "reason":"Leva giornaliera sui Treasury lunghi, sovrapposta ad altri bond duration lunga.",
            "checkpoint":"Controllare struttura ETF/CFD e costi prima di decidere.",
        })
    if any(h["symbol"]=="APT" and h["leverage"]>1 for h in holdings):
        actions.append({
            "priority":3,"severity":"ALTA","instrument":"APT",
            "verb":"VERIFICARE LEVA",
            "reason":"Posizione con esposizione superiore al valore di mercato indicato.",
            "checkpoint":"Confermare leverage, mercato, costi e possibile concentrazione.",
        })
    if totals["available_cash"]<100 or (equity>0 and totals["available_cash"]/equity<.03):
        actions.append({
            "priority":4,"severity":"MEDIA","instrument":"Nuove operazioni",
            "verb":"NESSUN NUOVO ACQUISTO",
            "reason":"Liquidità limitata e rischio già concentrato; nessun nuovo versamento previsto.",
            "checkpoint":"Non impegnare Fineco né aggiungere leva per recuperare perdite.",
        })
    if not actions:
        actions.append({
            "priority":1,"severity":"OSSERVAZIONE","instrument":"Portafoglio reale",
            "verb":"MANTENERE / MONITORARE",
            "reason":"Nessuna anomalia deducibile dalle soglie conservative.",
            "checkpoint":"Verificare costi, correlazioni e aggiornare lo snapshot.",
        })
    if not snapshot["fresh"]:
        actions=[
            {**a,"verb":"AGGIORNARE DATI PRIMA DI AGIRE",
             "checkpoint":"Snapshot oltre 36 ore: nessuna decisione eseguibile."}
            for a in actions
        ]
    return {
        "equity":equity,"cash":totals["available_cash"],
        "unrealized_pnl":totals["unrealized_pnl"],
        "used_margin":totals["used_margin"],"short_notional":short_notional,
        "short_count":short_count,"short_to_equity":risk_ratio,
        "margin_to_equity":used_margin_ratio,"fresh":snapshot["fresh"],
        "category_values":category_values,
        "stress":stress, "actions":actions,
        "holdings":sorted(holdings,key=lambda h:abs(h["exposure"]),reverse=True),
        "spx_positions":sorted(snapshot["positions"],key=lambda p:p["units"],reverse=True),
        "pending_orders_count":snapshot["pending_orders_count"],
        "reduction_pct":reduction,
        "as_of":snapshot["as_of"],
        "limitations":[
            "Scenari lineari solo sullo short SPX500, senza gap, altre posizioni o costi.",
            "Il rapporto margine utilizzato/equity NON è un livello di margin call.",
            "Ribilanciamento illustrativo, mai un ordine o una promessa di recupero.",
            "Conto eToro REALE, nessun versamento aggiuntivo, Fineco separato.",
        ],
    }
