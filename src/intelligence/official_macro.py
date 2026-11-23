"""Latest public CPI and industrial-production levels from US issuing agencies.

BLS SA CPI-U series CUSR0000SA0 maps to FRED CPIAUCSL.
FRB G.17 SA total industry code B50001 maps to FRED INDPRO.
These are distinct, dated primary-provider observations; never substitute
unrelated proxies, interpolate months or invent missing data.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
import math
import re
from urllib.request import Request, urlopen

CPI_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0"
IP_URL = "https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt"
OFFICIAL_SOURCES = {"CPIAUCSL": ("BLS", CPI_URL), "INDPRO": ("FRB-G17", IP_URL)}
MIN_MONTHS = 16
MAX_DAYS_OLD = 75


def _validated_monthly(code, observations, *, acquired_at, url):
    now = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("Timezone-aware acquisition timestamp required")
    if code not in OFFICIAL_SOURCES:
        raise ValueError("Unsupported primary-provider series")
    source, expected_url = OFFICIAL_SOURCES[code]
    if url != expected_url:
        raise ValueError("Provider URL mismatch")
    points = {}
    explicitly_unreported = set()
    for period, raw_value in observations:
        if not isinstance(period, date) or period.day != 1:
            raise ValueError("Macro periods must be first of month")
        if period > now.date():
            raise ValueError("Future observation period")
        if period in points or period in explicitly_unreported:
            raise ValueError("Duplicate monthly observation")
        if period < date(2023, 1, 1):
            continue
        # BLS explicitly reports a dash for unavailable CPI months.
        # Preserve the gap as missing, never replace with fabricated values.
        if code == "CPIAUCSL" and str(raw_value).strip() in ("-", ".", "", "N/A"):
            explicitly_unreported.add(period)
            continue
        value = float(raw_value)
        if not math.isfinite(value) or value <= 0 or value >= 1_000_000:
            raise ValueError("Invalid monthly observation")
        points[period] = value
    if len(points) < MIN_MONTHS:
        raise ValueError("Not enough actual monthly observations")
    keys = sorted(set(points) | explicitly_unreported)
    month_id = lambda d: d.year * 12 + d.month
    if any(month_id(b)-month_id(a)!=1 for a,b in zip(keys,keys[1:])):
        raise ValueError("Unreported monthly gap; no interpolation")
    if (code == "INDPRO" and explicitly_unreported) or len(explicitly_unreported) > 2:
        raise ValueError("Too many explicitly unreported macro months")
    last=max(points)
    age = (now.date()-last).days
    if not 0 <= age <= MAX_DAYS_OLD:
        raise ValueError(f"Source too stale: {last.isoformat()} ({age} days)")
    stream = StringIO()
    writer = csv.writer(stream,lineterminator="\n")
    writer.writerow(["observation_date",code])
    for d in keys:
        writer.writerow([d.isoformat(), format(points[d], ".12g") if d in points else ""])
    payload = stream.getvalue()
    return {
        "symbol": "FRED:"+code, "kind": "macro", "source": source,
        "source_url": url, "retrieved_at": acquired_at,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": payload,
    }


def parse_bls_cpi(payload, *, acquired_at, source_url=CPI_URL):
    doc = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(doc, dict) or doc.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError("BLS API did not confirm a successful response")
    results = doc.get("Results", {}).get("series", [])
    if len(results)!=1 or results[0].get("seriesID")!="CUSR0000SA0":
        raise ValueError("Unexpected BLS CPI series")
    pairs = []
    for item in results[0].get("data", []):
        if not isinstance(item, dict):
            raise ValueError("Invalid BLS observation")
        period = str(item.get("period", ""))
        if not re.fullmatch(r"M(0[1-9]|1[0-2])", period):
            continue  # M13 annual values must not be treated as monthly
        year = int(item["year"])
        month = int(period[1:])
        pairs.append((date(year,month,1),item["value"]))
    return _validated_monthly("CPIAUCSL",pairs,acquired_at=acquired_at,url=source_url)


def parse_g17_indpro(payload, *, acquired_at, source_url=IP_URL):
    text = payload.decode("ascii") if isinstance(payload,bytes) else payload
    if not isinstance(text, str) or len(text)>8_000_000:
        raise ValueError("Invalid/oversized G.17 history")
    if '"B50001: Total index"' not in text[:1000]:
        raise ValueError("G.17 total production index identification missing")
    points = []
    for line in text.splitlines():
        columns = line.strip().split()
        if not columns or columns[0] != '"B50001"':
            continue
        if len(columns) < 3:
            raise ValueError("G.17 year without observations")
        year = int(columns[1])
        if year < 2023:
            continue
        if len(columns)>14:
            raise ValueError("Unexpected G.17 row width")
        for month, value in enumerate(columns[2:],start=1):
            if month>12:
                raise ValueError("Unexpected 13th month")
            points.append((date(year,month,1),value))
    return _validated_monthly("INDPRO",points,acquired_at=acquired_at,url=source_url)


def _download(url, *, max_bytes, timeout=12, opener=None):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (TradingDesk-Research/1.0)",
                             "Accept": "application/json,text/plain"})
    with (opener or urlopen)(req,timeout=timeout) as response:
        content=response.read(max_bytes+1)
    if len(content)>max_bytes:
        raise ValueError("Source payload exceeds size limit")
    return content


def fetch_bls_cpi(*, now=None, opener=None):
    now=now or datetime.now(timezone.utc).isoformat()
    raw=_download(CPI_URL,max_bytes=400_000,timeout=9,opener=opener)
    return parse_bls_cpi(raw.decode("utf-8"),acquired_at=now)


def fetch_frb_indpro(*, now=None, opener=None):
    now=now or datetime.now(timezone.utc).isoformat()
    raw=_download(IP_URL,max_bytes=8_000_000,timeout=15,opener=opener)
    return parse_g17_indpro(raw,acquired_at=now)
