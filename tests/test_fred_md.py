"""Synthetic FRED-MD monthly-data tests; live endpoint verified separately in CI."""
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import pytest

from src.intelligence.fred_md import parse_fred_md, fetch_fred_md, OFFICIAL_URLS
from src.intelligence.macro import macro_context
from src.intelligence.refresh import import_record
from src.intelligence.store import Store

NOW = "2026-11-23T06:00:00+00:00"


def monthly_csv(*, missing=False, bad_gap=False):
    header = ["sasdate"] + [f"DUMMY_{i}" for i in range(20)]
    header += ["CPIAUCSL", "INDPRO"]
    result = [",".join(header), ",".join(["Transform:"] + ["1"] * (len(header) - 1))]
    for n, day in enumerate(pd.date_range("2025-05-01", periods=18, freq="MS")):
        if bad_gap and n == 5:
            continue
        row = [day.strftime("%m/%d/%Y")] + ["1"] * 20
        row += ["" if missing and n == 17 else f"{310+n:.4f}", f"{100+n/3:.4f}"]
        result.append(",".join(row))
    return "\n".join(result) + "\n"


def test_official_bundle_parses_two_real_series_without_imputation(tmp_path):
    records = parse_fred_md(monthly_csv(), acquired_at=NOW, source_url=OFFICIAL_URLS[0])
    assert sorted(records) == ["FRED:CPIAUCSL", "FRED:INDPRO"]
    assert all(r["source"] == "FRED-MD" and r["source_url"] == OFFICIAL_URLS[0] for r in records.values())
    assert records["FRED:CPIAUCSL"]["payload"].startswith("observation_date,CPIAUCSL\n")
    store=Store(tmp_path)
    for record in records.values():
        import_record(store,record,set(records))
    ctx=macro_context(store.latest_snapshots(),NOW)
    assert ctx["status"] == "DEGRADED"
    assert ctx["label"] != "Non disponibile"
    assert ctx["observations"].value.notna().sum() == 2


def test_missing_last_month_not_replaced_by_synthetic_value():
    records=parse_fred_md(monthly_csv(missing=True),acquired_at=NOW,source_url=OFFICIAL_URLS[0])
    assert records["FRED:CPIAUCSL"]["payload"].count("\n")==18  # 17 months + header
    assert "2026-10-01" not in records["FRED:CPIAUCSL"]["payload"]
    assert "2026-10-01" in records["FRED:INDPRO"]["payload"]


def test_gapped_months_are_not_accepted_as_continuous_release():
    with pytest.raises(ValueError, match="not qualified"):
        parse_fred_md(monthly_csv(bad_gap=True),acquired_at=NOW,source_url=OFFICIAL_URLS[0])


def test_schema_validation_rejects_mock_headers_and_wrong_provider(tmp_path):
    with pytest.raises(ValueError):
        parse_fred_md("date,foo\n2026-10-01,12",acquired_at=NOW,source_url=OFFICIAL_URLS[0])
    from src.intelligence.refresh import import_record
    r=parse_fred_md(monthly_csv(),acquired_at=NOW,source_url=OFFICIAL_URLS[0])["FRED:CPIAUCSL"]
    with pytest.raises(ValueError):
        import_record(Store(tmp_path),{**r,"source_url":"https://untrusted.invalid/"},{r["symbol"]})


def test_second_official_host_used_only_after_first_fails():
    calls=[]
    data=monthly_csv().encode()
    class Response:
        def __enter__(self): return self
        def __exit__(self,*_): return False
        def read(self,n): return data
    def opener(req,timeout):
        calls.append(req.full_url)
        if len(calls)==1:
            raise TimeoutError("first official host timed out")
        return Response()
    records=fetch_fred_md(now=NOW,open_url=opener)
    assert len(records)==2
    assert calls==list(OFFICIAL_URLS)
