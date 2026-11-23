"""Offline macro archive contracts: synthetic fixture values only."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from io import BytesIO

import pandas as pd

from src.intelligence import macro_archive, refresh
from src.intelligence.store import Store

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)


def record(code="CPIAUCSL", last="2026-10-01", retrieved="2026-11-22T10:00:00Z"):
    dates = pd.date_range("2025-05-01", periods=18, freq="MS")
    assert last == str(dates[-1].date())
    payload = "observation_date," + code + "\n" + "".join(
        f"{dt.date()},{100 + i}\n" for i, dt in enumerate(dates)
    )
    return {
        "symbol": "FRED:" + code, "kind": "macro", "source": "FRED",
        "source_url": f"https://fred.stlouisfed.org/series/{code}",
        "retrieved_at": retrieved,
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "payload": payload,
    }


def test_stored_official_observation_survives_provider_outage(tmp_path):
    r = record()
    store = Store(tmp_path)
    store.put_snapshot(**r)
    archive = macro_archive.build_archive(tmp_path, now=NOW)
    assert len(archive["records"]) == 1
    assert archive["records"][0]["sha256"] == r["sha256"]
    assert macro_archive.merge_archive(
        archive, {"schema_version": macro_archive.SCHEMA_VERSION, "records": []},
        now=NOW
    )["records"][0]["symbol"] == r["symbol"]


def test_hash_tampering_and_unknown_source_rejected():
    r = record()
    base = {"schema_version": macro_archive.SCHEMA_VERSION, "records": [r]}
    assert len(macro_archive.merge_archive({}, base, now=NOW)["records"]) == 1
    assert not macro_archive.merge_archive({}, {
        **base, "records": [{**r, "sha256": "f" * 64}]
    }, now=NOW)["records"]
    assert not macro_archive.merge_archive({}, {
        **base, "records": [{**r, "source_url": "https://attacker.example/"}]
    }, now=NOW)["records"]


def test_future_retrieval_and_wrong_series_never_import():
    bad = record(retrieved="2026-12-01T00:00:00Z")
    result = macro_archive.merge_archive(
        {}, {"schema_version": macro_archive.SCHEMA_VERSION, "records": [bad]},
        now=NOW
    )
    assert not result["records"]
    wrong = record()
    wrong["symbol"] = "FRED:INDPRO"
    assert not macro_archive.merge_archive(
        {}, {"schema_version": macro_archive.SCHEMA_VERSION, "records": [wrong]},
        now=NOW
    )["records"]


def test_bootstrap_reads_bounded_archive_and_no_bank_snapshots(tmp_path, monkeypatch):
    r = record()
    doc = json.dumps({"schema_version": macro_archive.SCHEMA_VERSION,
                      "assembled_at": NOW.isoformat(), "records": [r]}).encode()
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, *_): return doc
    monkeypatch.setattr(macro_archive, "urlopen", lambda request, timeout: Response())
    out = macro_archive.bootstrap_public_macro(tmp_path)
    assert out["status"] == "ARCHIVED" and out["imported"] == 1
    assert Store(tmp_path).latest_snapshots()["FRED:CPIAUCSL"]["payload"] == r["payload"]


def test_provider_timeout_keeps_previous_verified_archive(tmp_path, monkeypatch):
    r = record()
    Store(tmp_path).put_snapshot(**r)
    def outage(request, timeout):
        raise TimeoutError("declared network timeout")
    monkeypatch.setattr(macro_archive, "urlopen", outage)
    assert macro_archive.bootstrap_public_macro(tmp_path)["status"] == "UNAVAILABLE"
    assert Store(tmp_path).latest_snapshots()["FRED:CPIAUCSL"]["sha256"] == r["sha256"]


def test_optional_official_api_never_persists_secret(monkeypatch):
    r = record()
    monkeypatch.setenv("FRED_API_KEY", "synthetic-test-secret")
    monkeypatch.setattr(refresh, "_fred_api_payload",
                        lambda code, key: (r["payload"],
                            "https://api.stlouisfed.org/fred/series/observations?series_id=" + code))
    fetched = refresh.fetch_record("FRED:CPIAUCSL")
    assert fetched["sha256"] == r["sha256"]
    assert "synthetic-test-secret" not in json.dumps(fetched)
    assert fetched["kind"] == "macro"


def test_macro_circuit_limits_repeated_timeouts(tmp_path, monkeypatch):
    macro_codes = {f"CPIAUCSL": ("CPI", "index", 75),
                   "INDPRO": ("Industrial", "index", 75),
                   "DGS10": ("10y", "percentage", 7),
                   "DFII10": ("Real 10y", "percentage", 7)}
    monkeypatch.setattr(refresh, "SERIES", macro_codes)
    monkeypatch.setattr(refresh, "load_universe",
                        lambda root: pd.DataFrame({"symbol": ["SPY"]}))
    monkeypatch.setattr(refresh, "load_dashboard",
                        lambda root, include_unpublished: {
                            "metrics": pd.DataFrame({"price_status": []}),
                            "macro": {"status": "MISSING"}
                        })
    monkeypatch.setattr(refresh, "HORIZONS", ())
    called = []
    def outage(symbol):
        called.append(symbol)
        raise TimeoutError("declared provider timeout")
    monkeypatch.setattr(refresh, "fetch_record", outage)
    result = refresh.refresh_sources(tmp_path)
    macro_calls = [s for s in called if s.startswith("FRED:")]
    assert len(macro_calls) in (2, 3)
    assert any(e["error"] == "FredCircuitOpen" for e in result["errors"])
    assert result["acquired"] == 0
