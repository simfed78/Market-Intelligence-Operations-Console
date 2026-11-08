"""Pure eToro risk tests use fictitious account data, never production balances."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import json

import pytest

from src.intelligence.etoro_planner import (
    SCHEMA_VERSION, parse_private_snapshot, analyze_etoro,
)

NOW=datetime(2026,11,8,20,0,tzinfo=timezone.utc)


def fixture_snapshot():
    return {
        "schema_version":SCHEMA_VERSION,
        "account":"real","currency":"USD",
        "as_of":(NOW-timedelta(minutes=5)).isoformat(),
        "totals":{
            "equity":5000,"available_cash":50,"used_margin":2600,
            "unrealized_pnl":-850,
        },
        "holdings":[
            {"symbol":"SPX500","value":300,"exposure":-2500,"pnl":-700,
             "leverage":20,"position_count":1},
            {"symbol":"BOND","value":1800,"exposure":1800,"pnl":-30,
             "leverage":1,"position_count":3},
            {"symbol":"TMF","value":600,"exposure":600,"pnl":-60,
             "leverage":1,"position_count":2},
            {"symbol":"GLD","value":200,"exposure":200,"pnl":-20,
             "leverage":1,"position_count":1},
            {"symbol":"APT","value":50,"exposure":75,"pnl":-40,
             "leverage":1.5,"position_count":1},
        ],
        "positions":[
            {"position_id":1001,"symbol":"SPX500","direction":"short",
             "units":.5,"current_rate":5000,"pnl":-700,
             "leverage":20,"stop_loss":5600},
        ],
        "pending_orders_count":0,
        "api_secret":"NEVER-PUBLISH-THIS",
        "other_accounts":{"fineco":999999},
    }


def test_risk_math_from_spx_units_and_reported_exposure():
    snap=parse_private_snapshot(fixture_snapshot(),now=NOW)
    res=analyze_etoro(snap,reduction_pct=40)
    assert res["fresh"]
    assert res["short_notional"]==2500
    assert res["short_to_equity"]==.5
    assert res["stress"][0]["current_pnl"]==-50
    assert res["stress"][1]["current_pnl"]==-125
    assert res["stress"][1]["after_reduction_pnl"]==-75
    assert res["stress"][2]["current_pnl"]==-250
    assert res["cash"]==50
    assert res["used_margin"]==2600
    assert [x["instrument"] for x in res["actions"]]==[
        "SPX500 · short x20","TMF · Treasury 3x","APT","Nuove operazioni"
    ]
    assert "NEVER-PUBLISH" not in str(snap)
    assert "999999" not in str(snap)


@pytest.mark.parametrize("field,value",[
    ("account","demo"),("currency","EUR"),("schema_version","unknown"),
    ("as_of","2026-11-08"),("holdings",[]),("positions","wrong"),
    ("pending_orders_count",-1),
])
def test_invalid_structure_fails_closed(field,value):
    x=fixture_snapshot()
    x[field]=value
    with pytest.raises(ValueError):
        parse_private_snapshot(x,now=NOW)


@pytest.mark.parametrize("value",[-1,float("nan"),float("inf")])
def test_invalid_cash_or_margin_rejected(value):
    x=fixture_snapshot()
    x["totals"]["equity"]=value
    with pytest.raises(ValueError):
        parse_private_snapshot(x,now=NOW)


def test_missing_or_inconsistent_short_positions_fail_closed():
    x=fixture_snapshot()
    x["positions"][0]["units"]=1.5
    with pytest.raises(ValueError):
        parse_private_snapshot(x,now=NOW)
    x=fixture_snapshot()
    x["positions"][0]["position_id"]=-100
    with pytest.raises(ValueError):
        parse_private_snapshot(x,now=NOW)


def test_stale_snapshot_labels_all_recommendations_update_first():
    x=fixture_snapshot()
    x["as_of"]=(NOW-timedelta(days=3)).isoformat()
    snap=parse_private_snapshot(x,now=NOW)
    res=analyze_etoro(snap)
    assert not snap["fresh"]
    assert all(a["verb"]=="AGGIORNARE DATI PRIMA DI AGIRE" for a in res["actions"])
    assert res["stress"][1]["current_pnl"]==-125


def test_no_leveraged_short_and_zero_cash_does_not_invent_new_trades():
    x=fixture_snapshot()
    x["holdings"]=x["holdings"][1:3]
    x["positions"]=[]
    x["totals"]["available_cash"]=0
    snap=parse_private_snapshot(x,now=NOW)
    res=analyze_etoro(snap)
    assert res["short_notional"]==0
    assert res["stress"][2]["current_pnl"]==0
    assert all(a["verb"] not in ("ACQUISTA","BUY","SELL") for a in res["actions"])


def test_shock_is_monotone_in_hypothetical_risk_reduction():
    snap=parse_private_snapshot(fixture_snapshot(),now=NOW)
    losses=[abs(analyze_etoro(snap,reduction_pct=r)["stress"][2]["after_reduction_pnl"])
            for r in (0,40,70,100)]
    assert losses==sorted(losses,reverse=True) and losses[-1]==0
    with pytest.raises(ValueError):
        analyze_etoro(snap,reduction_pct=120)
