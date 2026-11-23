"""Official FRED-MD monthly-vintage fallback for public macro research.

FRED-MD is published by the Federal Reserve Bank of St. Louis and contains
CPIAUCSL and INDPRO. No synthetic observations, interpolations, or revisions
made here. The source's full raw CSV is never published in Git.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import math
from urllib.request import Request, urlopen

MONTHLY = ("CPIAUCSL", "INDPRO")
OFFICIAL_URLS = (
    "https://www.stlouisfed.org/-/media/project/frbstl/stlouisfed/research/fred-md/monthly/current.csv",
    "https://files.stlouisfed.org/files/htdocs/fred-md/monthly/current.csv",
)
MAX_BYTES = 5_000_000


def parse_fred_md(payload, *, acquired_at, source_url):
    """Select only untransformed government monthly levels; preserve provenance."""
    now = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("UTC acquisition time required")
    if not isinstance(payload, str) or len(payload) > MAX_BYTES:
        raise ValueError("FRED-MD body missing/oversized")
    reader = csv.reader(StringIO(payload.lstrip("\ufeff")))
    header = next(reader, [])
    if (not header or header[0].strip().lower() != "sasdate"
            or not all(code in header for code in MONTHLY)
            or len(header) < 20):
        raise ValueError("Not an official FRED-MD monthly CSV schema")
    positions = {code: header.index(code) for code in MONTHLY}
    series = {code: [] for code in MONTHLY}
    for row in reader:
        if not row or row[0].strip().lower() in ("transform:", "transform"):
            continue
        try:
            period = datetime.strptime(row[0].strip(), "%m/%d/%Y").date()
        except ValueError:
            try:
                period = date.fromisoformat(row[0].strip())
            except ValueError:
                continue
        if period > now.date() or period < date(2023, 1, 1):
            continue
        period = period.replace(day=1)
        for code, i in positions.items():
            try:
                value = float(row[i])
            except (IndexError, ValueError):
                continue
            if not (math.isfinite(value) and 0 < value < 1_000_000):
                continue
            series[code].append((period, value))
    result = {}
    for code, values in series.items():
        if len(values) < 16 or values != sorted(values):
            continue
        if len({dt for dt, _ in values}) != len(values):
            continue
        month_id = lambda dt: dt.year * 12 + dt.month
        if any(month_id(b[0])-month_id(a[0]) != 1 for a,b in zip(values,values[1:])):
            continue
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["observation_date", code])
        for day, val in values:
            writer.writerow([day.isoformat(), format(val, ".12g")])
        serialized = buffer.getvalue()
        result["FRED:" + code] = {
            "symbol": "FRED:" + code, "retrieved_at": acquired_at,
            "source": "FRED-MD", "source_url": source_url,
            "kind": "macro", "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
            "payload": serialized,
        }
    if not result:
        raise ValueError("FRED-MD CPI/INDPRO observations not qualified")
    return result


def fetch_fred_md(*, now=None, open_url=None):
    """Bounded direct official endpoint requests; fail closed if both unavailable."""
    now = now or datetime.now(timezone.utc).isoformat()
    opener = open_url or urlopen
    failures = []
    for url in OFFICIAL_URLS:
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (TradingDesk-Macro-Research/1.0)",
                                             "Accept": "text/csv,text/plain"})
            with opener(request, timeout=11) as response:
                payload_bytes = response.read(MAX_BYTES + 1)
            if len(payload_bytes) > MAX_BYTES:
                raise ValueError("Official FRED-MD CSV oversized")
            result = parse_fred_md(payload_bytes.decode("utf-8-sig"), acquired_at=now,
                                   source_url=url)
            if not all(symbol in result for symbol in ("FRED:CPIAUCSL", "FRED:INDPRO")):
                raise ValueError("Monthly source missing CPI/INDPRO requirements")
            evaluated=datetime.fromisoformat(now.replace("Z","+00:00"))
            for record in result.values():
                last_day=date.fromisoformat(record["payload"].splitlines()[-1].split(",")[0])
                age=(evaluated.date()-last_day).days
                if not 0<=age<=75:
                    raise ValueError("FRED-MD published series is stale: "
                                     +record["symbol"]+" observed "+last_day.isoformat())
            return result
        except (OSError, UnicodeError, ValueError) as exc:
            failures.append(type(exc).__name__)
    raise ConnectionError("Official FRED-MD URLs unavailable or invalid: " + ",".join(failures))
