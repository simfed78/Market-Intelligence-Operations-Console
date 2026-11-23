"""Synthetic fixtures: verify offline derived macro, not redistribution of FRED data."""
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd

from src.intelligence import macro_archive, refresh
from src.intelligence.store import Store

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)


def record(code="CPIAUCSL", retrieved="2026-11-22T10:00:00Z"):
    dates = pd.date_range("2025-05-01", periods=18, freq="MS")
    payload = "observation_date," + code + "\n" + "".join(
        f"{dt.date()},{100 + i}\n" for i, dt in enumerate(dates)
    )
    return {
        "symbol": "FRED:" + code, "kind": "macro", "source": "FRED",
        "source_url": f"https://fred.stlouisfed.org/series/{code}",
        "retrieved_at": retrieved,
        "sha256": hashlib.sha256(payload.encode()).hexdigest(), "payload": payload,
    }


def build(tmp_path, *codes):
    store = Store(tmp_path)
    for code in codes:
        store.put_snapshot(**record(code))
    return macro_archive.build_archive(tmp_path, now=NOW)


def test_archive_retains_verified_source_metadata_not_raw_observations(tmp_path):
    document = build(tmp_path, "CPIAUCSL", "INDPRO")
    assert macro_archive._valid(document, now=NOW)
    assert len(document["observations"]) == 2
    assert "payload" not in json.dumps(document)
    assert "observation_date" not in json.dumps(document)
    assert all("value" not in item for item in document["observations"])
    assert all(len(item["input_sha256"]) == 64 for item in document["observations"])
    assert document["derived_regime"]["label"] is not None


def test_missing_new_observations_cannot_erase_previous_archive(tmp_path):
    old = build(tmp_path, "CPIAUCSL")
    merged = macro_archive.merge_archive(old, {}, now=NOW)
    assert merged["observations"] == old["observations"]
    assert macro_archive._valid(merged, now=NOW)


def test_tampered_source_and_raw_values_rejected(tmp_path):
    archive = build(tmp_path, "CPIAUCSL")
    forged = json.loads(json.dumps(archive))
    forged["observations"][0]["value"] = 99.0
    forged["integrity_sha256"] = macro_archive._digest(forged)
    assert not macro_archive._valid(forged, now=NOW)
    forged2 = json.loads(json.dumps(archive))
    forged2["observations"][0]["source_url"] = "https://untrusted.example"
    forged2["integrity_sha256"] = macro_archive._digest(forged2)
    assert not macro_archive._valid(forged2, now=NOW)


def test_future_archive_rejected(tmp_path):
    a = build(tmp_path, "CPIAUCSL")
    a["compiled_at"] = "2026-12-01T00:00:00Z"
    a["integrity_sha256"] = macro_archive._digest(a)
    assert not macro_archive._valid(a, now=NOW)


def test_bootstrap_stores_derived_only_and_preserves_dated_metadata(tmp_path, monkeypatch):
    archive = build(tmp_path, "CPIAUCSL", "INDPRO")
    raw = json.dumps(archive).encode()
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, *_): return raw
    monkeypatch.setattr(macro_archive, "urlopen", lambda request, timeout: Response())
    result = macro_archive.bootstrap_public_macro(tmp_path, now=NOW)
    assert result == {"status": "ARCHIVED", "imported": 2}
    assert not Store(tmp_path).latest_snapshots().get("FRED:NON_EXISTENT")
    restored = macro_archive.archived_macro_context(tmp_path, as_of=NOW)
    assert restored["label"] != "Non disponibile"
    assert restored["archived"] is True
    assert restored["observations"].value.isna().all()
    assert restored["observations"].status.eq("ARCHIVED_METADATA").sum() == 2


def test_timeout_cannot_destroy_previous_derived_summary(tmp_path, monkeypatch):
    archive = build(tmp_path, "CPIAUCSL")
    macro_archive.atomic_json(tmp_path / macro_archive.LOCAL_COPY, archive)
    monkeypatch.setattr(macro_archive, "urlopen",
                        lambda request, timeout: (_ for _ in ()).throw(TimeoutError("network down")))
    assert macro_archive.bootstrap_public_macro(tmp_path)["status"] == "UNAVAILABLE"
    assert macro_archive.archived_macro_context(tmp_path, as_of=NOW) is not None


def test_optional_official_api_never_persists_secret(monkeypatch):
    r = record()
    monkeypatch.setenv("FRED_API_KEY", "synthetic-test-secret")
    monkeypatch.setattr(refresh, "_fred_api_payload",
                        lambda code, key: (r["payload"],
                          "https://api.stlouisfed.org/fred/series/observations?series_id=" + code))
    fetched = refresh.fetch_record("FRED:CPIAUCSL")
    assert fetched["sha256"] == r["sha256"]
    assert "synthetic-test-secret" not in json.dumps(fetched)


def test_macro_circuit_limits_repeated_timeouts(tmp_path, monkeypatch):
    macro_codes = {"CPIAUCSL": ("CPI", "index", 75),
                   "INDPRO": ("Industrial", "index", 75),
                   "DGS10": ("10y", "percent", 7),
                   "DFII10": ("Real", "percent", 7)}
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
    assert len(macro_calls) == 2
    assert any(item["error"] == "FredCircuitOpen" for item in result["errors"])
    assert result["acquired"] == 0
