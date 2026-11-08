"""Offline, synthetic-input tests for the session-private Fineco planner."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import pandas as pd
import pytest

from src.intelligence.fineco_planner import (
    FINECO_POSITIONS, BUY_SET, MAX_SNAPSHOT_AGE_HOURS, build_fineco_plan, dashboard_from_public_brief,
)

NOW = datetime(2026, 11, 8, 13, tzinfo=timezone.utc)


def research_data(*, world="RESEARCH CANDIDATE", gold="WATCHLIST"):
    metrics = pd.DataFrame([{"symbol": s, "price_status":"VALID"}
                            for s in ("VT", "ACWI", "GLD", "IAU", "USO", "DBC", "XLV", "XLP")])
    opportunities = {}
    for horizon in ("1m","3m","6m","12m"):
        rows = []
        for symbol, status in (
            ("VT",world),("ACWI",world),("GLD",gold),("IAU",gold),
            ("USO","RESEARCH CANDIDATE"),("DBC","RESEARCH CANDIDATE"),
            ("XLV","RESEARCH CANDIDATE"),("XLP","RESEARCH CANDIDATE"),
        ):
            rows.append(dict(
                symbol=symbol, price_status="VALID", model_version="technical-priority-v1",
                signal_state=status, technical_score=75 if status=="RESEARCH CANDIDATE" else 40,
                timing_score=100 if status=="RESEARCH CANDIDATE" else 0,
                observed_at="2026-11-06"
            ))
        opportunities[horizon] = pd.DataFrame(rows)
    return dict(
        metrics=metrics,
        latest_run={"run_at":(NOW-timedelta(hours=2)).isoformat()},
        opportunities=opportunities, macro={"status":"MISSING"},
        core={"personal_balance":99999}, broker={"account":"PRIVATE"},
    )


def positions():
    return {"VALL":21.4,"PRAB":65.5,"EUR_GOV":612.56,"LIFESTRATEGY60":442.8,
            "UST01":430.24,"METALS":46.21,"ROBOTICS":45.43,"SGLN":0}


def test_only_three_new_products_and_no_sector_lookthrough():
    assert len(FINECO_POSITIONS) <= 10
    assert BUY_SET == ("VALL","PRAB","SGLN")
    plan = build_fineco_plan(
        research_data(),available_cash_eur=1000,cash_confirmed=True,
        holdings=positions(),holdings_confirmed=True,now=NOW,
    )
    assert plan["plan_ready"]
    assert {r["code"] for r in plan["rows"]} == set(BUY_SET)
    assert all(r["action"] != "BUY" for r in plan["rows"])
    assert "USO" not in [r["code"] for r in plan["rows"]]
    assert "XLV" not in [r["code"] for r in plan["rows"]]
    assert [r["proposed_eur"] for r in plan["rows"]] == [450,350,0]
    assert plan["kept_cash_eur"] == 200
    assert abs(sum(r["proposed_eur"] for r in plan["rows"]) + plan["kept_cash_eur"] - 1000) < 1e-6
    assert plan["signals"]["gold_3m"]["state"] == "DEBOLE"
    assert plan["signals"]["world_12m"]["state"] == "FAVOREVOLE"


def test_no_money_before_salary_or_before_manual_confirmation():
    case = research_data()
    p = positions()
    for budget, cash_ok, holdings_ok in (
        (0,True,True),(1000,False,True),(1000,True,False),
    ):
        r = build_fineco_plan(
            case, available_cash_eur=budget,cash_confirmed=cash_ok,
            holdings=p,holdings_confirmed=holdings_ok,now=NOW,
        )
        assert not r["plan_ready"] and r["suggested_eur"]==0
        assert all(x["action"]=="ATTENDERE" for x in r["rows"])


@pytest.mark.parametrize("mutation",["no_run","stale_run","future_run","low_quality","no_rankings"])
def test_stale_or_missing_market_data_freeze_every_suggested_purchase(mutation):
    case = research_data()
    if mutation=="no_run":case["latest_run"]=None
    if mutation=="stale_run":case["latest_run"]["run_at"]=(NOW-timedelta(hours=MAX_SNAPSHOT_AGE_HOURS+1)).isoformat()
    if mutation=="future_run":case["latest_run"]["run_at"]=(NOW+timedelta(minutes=1)).isoformat()
    if mutation=="low_quality":case["metrics"]["price_status"]="MISSING"
    if mutation=="no_rankings":case["opportunities"]={}
    r=build_fineco_plan(case,available_cash_eur=1000,cash_confirmed=True,
                        holdings=positions(),holdings_confirmed=True,now=NOW)
    if mutation=="no_rankings":
        # Fresh underlying series but no qualified world or gold research:
        # the defensive EUR sleeve may be considered, never invented equity/gold.
        assert r["plan_ready"]
        assert r["rows"][0]["proposed_eur"]==0 and r["rows"][2]["proposed_eur"]==0
    else:
        assert not r["plan_ready"] and r["suggested_eur"]==0


def test_existing_equity_concentration_blocks_new_equity_adds():
    p=positions();p["VALL"]=3000
    r=build_fineco_plan(research_data(),available_cash_eur=1000,
                       cash_confirmed=True,holdings=p,holdings_confirmed=True,now=NOW)
    assert r["rows"][0]["proposed_eur"]==0
    assert r["kept_cash_eur"] >= 450


def test_gold_positive_but_small_tranche_does_not_generate_costly_order():
    r=build_fineco_plan(
        research_data(gold="RESEARCH CANDIDATE"),available_cash_eur=1000,
        cash_confirmed=True,holdings=positions(),holdings_confirmed=True,now=NOW,
    )
    gold=next(x for x in r["rows"] if x["code"]=="SGLN")
    assert gold["proposed_eur"]==0
    assert gold["action"]=="ACCUMULARE LIQUIDITÀ"
    # At larger available balances, gold is no longer stranded below minimum.
    bigger=build_fineco_plan(
        research_data(gold="RESEARCH CANDIDATE"),available_cash_eur=2000,
        cash_confirmed=True,holdings=positions(),holdings_confirmed=True,now=NOW,
    )
    assert next(x for x in bigger["rows"] if x["code"]=="SGLN")["proposed_eur"]==200


def test_negative_nan_unknown_and_broker_fields_are_not_accepted_or_exposed():
    with pytest.raises(ValueError):
        build_fineco_plan(research_data(), available_cash_eur=-100, now=NOW)
    with pytest.raises(ValueError):
        build_fineco_plan(research_data(), holdings={"UNEXPECTED":200}, now=NOW)
    with pytest.raises(ValueError):
        build_fineco_plan(research_data(), holdings={"VALL":float("nan")}, now=NOW)
    p=build_fineco_plan(research_data(),available_cash_eur=1000,
                        cash_confirmed=True,holdings=positions(),holdings_confirmed=True,now=NOW)
    assert "PRIVATE" not in str(p) and "99999" not in str(p)


def test_research_data_branch_contract_can_drive_same_pure_planner():
    local=research_data()
    brief={
        "schema_version":"research-brief.v1",
        "mode":"RESEARCH_ONLY",
        "publication_status":"QUALIFIED_RESEARCH",
        "model_version":"technical-priority-v1",
        "generated_at":(NOW-timedelta(minutes=30)).isoformat(),
        "completed_run_at":(NOW-timedelta(hours=1)).isoformat(),
        "quality":{"valid_ratio":.9379,"macro_status":"MISSING"},
        "horizons":{}
    }
    for horizon in ("3m","12m"):
        brief["horizons"][horizon]={"fineco_proxies":local["opportunities"][horizon].to_dict("records")}
    remote=dashboard_from_public_brief(brief,now=NOW)
    assert remote["source_kind"]=="qualified-public-export"
    assert remote["quality"]["valid_ratio"]==.9379
    plan=build_fineco_plan(remote,available_cash_eur=1000,cash_confirmed=True,
                          holdings=positions(),holdings_confirmed=True,now=NOW)
    assert plan["plan_ready"] and plan["suggested_eur"]==800
    assert plan["signals"]["commodities_3m"]["state"]=="FAVOREVOLE"
    assert all("private" not in str(v).lower() for v in remote.values())


@pytest.mark.parametrize("change",["stale","missing_proxies","bad_model","poor_quality","future"])
def test_public_export_rejected_without_qualified_fresh_proxies(change):
    local=research_data()
    brief={
        "schema_version":"research-brief.v1","mode":"RESEARCH_ONLY",
        "publication_status":"QUALIFIED_RESEARCH","model_version":"technical-priority-v1",
        "generated_at":(NOW-timedelta(minutes=10)).isoformat(),
        "completed_run_at":(NOW-timedelta(hours=1)).isoformat(),
        "quality":{"valid_ratio":.9,"macro_status":"MISSING"},
        "horizons":{h:{"fineco_proxies":local["opportunities"][h].to_dict("records")} for h in ("3m","12m")}
    }
    if change=="stale":brief["generated_at"]=(NOW-timedelta(days=4)).isoformat();brief["completed_run_at"]=(NOW-timedelta(days=4,minutes=5)).isoformat()
    if change=="missing_proxies":brief["horizons"]["3m"].pop("fineco_proxies")
    if change=="bad_model":brief["model_version"]="unvalidated-v99"
    if change=="poor_quality":brief["quality"]["valid_ratio"]=.3
    if change=="future":brief["generated_at"]=(NOW+timedelta(minutes=1)).isoformat()
    with pytest.raises((ValueError,TypeError)):
        dashboard_from_public_brief(brief,now=NOW)
