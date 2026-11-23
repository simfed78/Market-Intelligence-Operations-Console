"""Public-sector CPI/IP acquisition contracts using deterministic fixtures."""
from datetime import date
import json

import pandas as pd
import pytest

from src.intelligence.official_macro import (
    CPI_URL, IP_URL, parse_bls_cpi, parse_g17_indpro,
    fetch_bls_cpi, fetch_frb_indpro,
)
from src.intelligence.refresh import import_record
from src.intelligence.macro import macro_context
from src.intelligence.store import Store

NOW = "2026-11-23T08:00:00+00:00"


def sample_bls(*, end="2026-10-01", months=18):
    dates=pd.date_range(end=end, periods=months, freq="MS")
    return {"status":"REQUEST_SUCCEEDED",
            "Results":{"series":[{"seriesID":"CUSR0000SA0",
                                  "data":[{"year":str(day.year),"period":f"M{day.month:02d}",
                                           "value":f"{310+i:.3f}"}
                                          for i,day in enumerate(dates)]}]}}


def sample_g17():
    return '"B50001: Total index"\n' + "\n".join(
        ['"B50001" 2025 ' + " ".join(f"{100+i*.1:.4f}" for i in range(12)),
         '"B50001" 2026 ' + " ".join(f"{101+i*.1:.4f}" for i in range(10))]
    )


def test_bls_and_g17_are_distinct_issuer_sources(tmp_path):
    cpi=parse_bls_cpi(sample_bls(),acquired_at=NOW)
    ip=parse_g17_indpro(sample_g17(),acquired_at=NOW)
    assert cpi["symbol"]=="FRED:CPIAUCSL" and cpi["source"]=="BLS"
    assert ip["symbol"]=="FRED:INDPRO" and ip["source"]=="FRB-G17"
    assert cpi["source_url"]==CPI_URL and ip["source_url"]==IP_URL
    store=Store(tmp_path)
    for rec in (cpi,ip):
        import_record(store,rec,{rec["symbol"]})
    ctx=macro_context(store.latest_snapshots(),NOW)
    assert ctx["label"]!="Non disponibile"
    assert ctx["status"]=="DEGRADED"
    assert ctx["observations"].value.notna().sum()==2


def test_bls_schema_and_freshness_are_required():
    with pytest.raises(ValueError):
        parse_bls_cpi({**sample_bls(),"status":"REQUEST_FAILED"},acquired_at=NOW)
    with pytest.raises(ValueError):
        parse_bls_cpi(sample_bls(end="2025-10-01"),acquired_at=NOW)
    with pytest.raises(ValueError):
        parse_bls_cpi(sample_bls(months=12),acquired_at=NOW)
    corrupted=sample_bls()
    corrupted["Results"]["series"][0]["seriesID"]="CUSR9999"
    with pytest.raises(ValueError):
        parse_bls_cpi(corrupted,acquired_at=NOW)


def test_g17_cannot_be_other_series_or_missing_months():
    with pytest.raises(ValueError):
        parse_g17_indpro(sample_g17().replace("B50001","B50030"),acquired_at=NOW)
    with pytest.raises(ValueError):
        parse_g17_indpro(sample_g17().replace("2026 ",'2024 '),acquired_at=NOW)
    with pytest.raises(ValueError):
        parse_g17_indpro(sample_g17()+'\n"B50001" 2026 999.0',acquired_at=NOW)


def test_provider_url_is_pinned_and_cannot_be_forged(tmp_path):
    record=parse_bls_cpi(sample_bls(),acquired_at=NOW)
    with pytest.raises(ValueError):
        import_record(Store(tmp_path),{**record,"source_url":"https://example.invalid/"},
                      {record["symbol"]})
    with pytest.raises(ValueError):
        import_record(Store(tmp_path),{**record,"source":"FRB-G17"},
                      {record["symbol"]})


def test_bls_missing_or_nonfinite_month_not_interpolated():
    payload=sample_bls()
    payload["Results"]["series"][0]["data"][7]["value"]="."
    with pytest.raises(ValueError):
        parse_bls_cpi(payload,acquired_at=NOW)


def test_bounded_http_reads_are_parsed_and_provenanced():
    class Response:
        def __init__(self,payload):self.payload=payload
        def __enter__(self):return self
        def __exit__(self,*_):return False
        def read(self,n):return self.payload
    def opener(req,timeout):
        if req.full_url==CPI_URL:
            return Response(json.dumps(sample_bls()).encode())
        assert req.full_url==IP_URL
        return Response(sample_g17().encode())
    assert fetch_bls_cpi(now=NOW,opener=opener)["source"]=="BLS"
    assert fetch_frb_indpro(now=NOW,opener=opener)["source"]=="FRB-G17"
