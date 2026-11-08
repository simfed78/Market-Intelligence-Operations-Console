"""Pure, offline checks for the public research export contract."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pandas as pd
import pytest

from src.intelligence.opportunities import HORIZONS, rank_opportunities
from src.intelligence.report_export import (
    ASSET_FIELDS, SCHEMA_VERSION, atomic_json, build_brief,
)

NOW = datetime(2026, 11, 8, 11, 0, tzinfo=timezone.utc)


def prepared_data():
    rows = []
    for asset_class in ("Azioni", "Obbligazioni", "Commodities"):
        for i in range(3):
            rows.append({
                "symbol": f"{asset_class[:2].upper()}{i}",
                "name": "Declared test asset",
                "kind": "ETF",
                "asset_class": asset_class,
                "region": "TEST",
                "currency": "USD",
                "price_status": "VALID",
                "volume_status": "VALID",
                "ranking_eligible": True,
                "risk_score": 20 + i * 10,
                "timing_score": 100,
                "momentum_1m": 65 + i * 5,
                "momentum_3m": 65 + i * 5,
                "momentum_6m": 65 + i * 5,
                "momentum_12m": 65 + i * 5,
                "clientId": "PRIVATE-ACCOUNT-ID",
                "broker_balance": 999999,
                "secret_token": "SENSITIVE-EXAMPLE-KEY",
                "source_url": "https://private.invalid/broker",
                "raw_prices": [100, 101, 102],
                "source": "Declared unit fixture",
            })
    metrics = pd.DataFrame(rows)
    rankings = {h: rank_opportunities(metrics, h) for h in HORIZONS}
    return {
        "metrics": metrics,
        "opportunities": rankings,
        "latest_run": {
            "run_at": (NOW - timedelta(hours=1)).isoformat(),
            "acquired": 9,
            "cached": 0,
            "errors": [],
        },
        "macro": {"status": "MISSING", "private_key": "DO-NOT-PUBLISH"},
        "core": {"balance": 12345678, "clientId": "SECRET-CORE"},
    }


def test_four_horizons_and_source_quality_are_explicit():
    brief = build_brief(prepared_data(), now=NOW)
    assert brief["schema_version"] == SCHEMA_VERSION
    assert brief["mode"] == "RESEARCH_ONLY"
    assert brief["publication_status"] == "QUALIFIED_RESEARCH"
    assert set(brief["horizons"]) == set(HORIZONS)
    assert brief["quality"]["price_valid"] == 9
    assert brief["quality"]["macro_status"] == "MISSING"
    for horizon in HORIZONS:
        section = brief["horizons"][horizon]
        assert section["eligible_count"] == 9
        assert set(section["leaders_by_asset_class"]) == {"Azioni", "Obbligazioni", "Commodities"}
        for item in section["top10"]:
            assert set(item) == set(ASSET_FIELDS)
            assert item["price_status"] == "VALID"
            assert item["signal_state"] in ("RESEARCH CANDIDATE", "WATCHLIST")
            assert item["model_version"] == "technical-priority-v1"


def test_proprietary_account_and_raw_market_records_never_leak():
    brief = build_brief(prepared_data(), now=NOW)
    text = json.dumps(brief, allow_nan=False)
    for forbidden in (
        "PRIVATE-ACCOUNT-ID", "SENSITIVE-EXAMPLE-KEY", "SECRET-CORE",
        "DO-NOT-PUBLISH", "broker_balance", "raw_prices", "private.invalid",
    ):
        assert forbidden not in text
    assert "ENTRY CANDIDATE" not in text


@pytest.mark.parametrize("failure", [
    "no_run", "stale_run", "future_run", "no_acquisition",
    "low_coverage", "no_opportunities",
])
def test_missing_or_stale_inputs_fail_closed(failure):
    data = prepared_data()
    if failure == "no_run":
        data["latest_run"] = None
    elif failure == "stale_run":
        data["latest_run"]["run_at"] = (NOW - timedelta(days=2)).isoformat()
    elif failure == "future_run":
        data["latest_run"]["run_at"] = (NOW + timedelta(minutes=1)).isoformat()
    elif failure == "no_acquisition":
        data["latest_run"]["acquired"] = 0
        data["latest_run"]["cached"] = 0
    elif failure == "low_coverage":
        data["metrics"].loc[:4, "price_status"] = "MISSING"
    elif failure == "no_opportunities":
        data["opportunities"] = {}
    with pytest.raises(ValueError):
        build_brief(data, now=NOW)


def test_atomic_snapshot_write_is_valid_json_and_retains_existing_on_failure(tmp_path):
    dest = tmp_path / "public" / "latest.json"
    good = build_brief(prepared_data(), now=NOW)
    atomic_json(dest, good)
    before = dest.read_bytes()
    assert json.loads(before)["schema_version"] == SCHEMA_VERSION
    bad = prepared_data()
    bad["latest_run"] = None
    with pytest.raises(ValueError):
        atomic_json(dest, build_brief(bad, now=NOW))
    assert dest.read_bytes() == before


def test_deterministic_research_rankings_across_input_row_orders():
    first = prepared_data()
    second = prepared_data()
    second["metrics"] = second["metrics"].sample(frac=1, random_state=14)
    second["opportunities"] = {
        h: rank_opportunities(second["metrics"], h) for h in HORIZONS
    }
    a = build_brief(first, now=NOW)
    b = build_brief(second, now=NOW)
    assert a == b
