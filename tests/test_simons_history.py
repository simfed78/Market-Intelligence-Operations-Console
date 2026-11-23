"""Independent long-history parsing and calendar tests using synthetic fixtures."""
from datetime import datetime, timezone
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

xcals = pytest.importorskip("exchange_calendars")

from src.intelligence.simons_history import normalize_long_snapshot

AS_OF = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


def record_fixture():
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range("2022-01-03", "2026-11-20")[-750:]
    timestamps = [
        int(pd.Timestamp(f"{s.date()}T16:00:00", tz="America/New_York").timestamp())
        for s in sessions
    ]
    n = len(sessions)
    prices = (100 * np.exp(np.arange(n) * 0.0004)).tolist()
    data = {"chart": {"result": [{
        "meta": {"symbol": "SPY", "instrumentType": "ETF",
                 "exchangeName": "PCX", "exchangeTimezoneName": "America/New_York"},
        "timestamp": timestamps,
        "indicators": {
            "quote": [{"open": prices, "high": [x * 1.005 for x in prices],
                       "low": [x * .995 for x in prices], "close": prices,
                       "volume": [100_000] * n}],
            "adjclose": [{"adjclose": prices}]
        }
    }]}}
    payload = json.dumps(data)
    return {"source": "Yahoo Finance", "retrieved_at": "2026-11-21T12:00:00Z",
            "kind": "market", "symbol": "SPY", "payload": payload,
            "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "source_url": "https://query1.finance.yahoo.com/v8/finance/chart/SPY"}


def test_complete_five_year_data_fixture_qualifies():
    frame, meta = normalize_long_snapshot(record_fixture(), "SPY", as_of=AS_OF)
    assert len(frame) == 750
    assert meta["price_status"] == "VALID"
    assert meta["calendar"] == "XNYS exchange_calendars"


def test_content_hash_mismatch_is_rejected():
    record = record_fixture()
    record["payload"] += " "
    frame, meta = normalize_long_snapshot(record, "SPY", as_of=AS_OF)
    assert frame.empty and meta["price_status"] == "DEGRADED"


def test_missing_historical_session_fails_closed():
    record = record_fixture()
    data = json.loads(record["payload"])
    row = data["chart"]["result"][0]
    row["timestamp"].pop(100)
    for category in ("quote", "adjclose"):
        vals = row["indicators"][category][0]
        for key in vals:
            vals[key].pop(100)
    record["payload"] = json.dumps(data)
    record["sha256"] = hashlib.sha256(record["payload"].encode()).hexdigest()
    frame, meta = normalize_long_snapshot(record, "SPY", as_of=AS_OF)
    assert frame.empty and meta["price_status"] == "DEGRADED"
