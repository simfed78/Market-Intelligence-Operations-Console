"""Independent long-history adapter for Simons research; never touches ranking DB.

Raw Yahoo chart snapshots are retained only in local data/simons_history, not
in the public Streamlit Store or published artifacts. Exchange calendar is
verified with exchange_calendars XNYS, independent of the bounded 2024-27
calendar required by the Phase 3 dashboard.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from zoneinfo import ZoneInfo
import hashlib
import json
import re

import numpy as np
import pandas as pd

from src.intelligence.simons_quant import evaluate_history, _abstain, _utc, VERSION


def _path(root, symbol):
    if not re.fullmatch(r"[A-Za-z0-9^._=-]{1,32}", symbol):
        raise ValueError("Symbol contains unsafe characters")
    return Path(root) / "data" / "simons_history" / f"{symbol}.json"


def fetch_long_snapshot(symbol, *, years=5):
    """Explicit, source-labelled public Yahoo daily data download; no credentials."""
    if years not in (5, 10):
        raise ValueError("Only 5y or 10y research horizons are allowed")
    if not re.fullmatch(r"[A-Za-z0-9^._=-]{1,32}", symbol):
        raise ValueError("Unsafe symbol")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{quote(symbol, safe='')}?range={years}y&interval=1d&events=div%2Csplits")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (TradingDesk QuantResearch/1.0)"})
    with urlopen(request, timeout=25) as response:
        payload = response.read().decode("utf-8")
    result = json.loads(payload).get("chart", {}).get("result")
    if not result or result[0].get("meta", {}).get("symbol", "").upper() != symbol.upper():
        raise ValueError("Yahoo did not return the requested symbol")
    return {"source": "Yahoo Finance", "source_url": url, "kind": "market",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "payload": payload, "symbol": symbol}


def save_long_snapshot(root, record):
    p = _path(root, record["symbol"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record), encoding="utf-8")
    return p


def load_long_snapshot(root, symbol):
    p = _path(root, symbol)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def normalize_long_snapshot(record, symbol, *, as_of):
    """Qualified XNYS-calendar history, not an execution or PIT certificate."""
    empty = pd.DataFrame()
    meta = {"source": None, "retrieved_at": None, "price_status": "MISSING",
            "reason": "No qualified long-history data"}
    stamp = _utc(as_of)
    if not isinstance(record, dict) or stamp is None:
        return empty, meta
    retrieved = _utc(record.get("retrieved_at"))
    if (retrieved is None or retrieved > stamp
            or (stamp - retrieved).total_seconds() > 5 * 86400
            or record.get("source") != "Yahoo Finance"
            or record.get("kind") != "market"
            or record.get("symbol", "").upper() != symbol.upper()):
        return empty, {**meta, "price_status": "DEGRADED",
                       "reason": "Bad acquisition time or provider provenance"}
    payload = record.get("payload")
    if (not isinstance(payload, str) or
            hashlib.sha256(payload.encode()).hexdigest() != record.get("sha256")):
        return empty, {**meta, "price_status": "DEGRADED",
                       "reason": "Snapshot content hash mismatch"}
    try:
        import exchange_calendars as xcals
        chart = json.loads(payload)["chart"]["result"][0]
        provider = chart["meta"]
        if provider["symbol"].upper() != symbol.upper():
            raise ValueError("Provider symbol mismatch")
        if provider.get("instrumentType") not in {"ETF", "EQUITY"}:
            raise ValueError("Only US-listed ETF/EQUITY history supported")
        if provider.get("exchangeName") not in {"PCX", "NMS", "NGM", "NCM", "NYQ", "ASE", "BTS", "BATS"}:
            raise ValueError("Unsupported US-listed exchange")
        tz = ZoneInfo(provider.get("exchangeTimezoneName", "America/New_York"))
        dates = (pd.to_datetime(chart["timestamp"], unit="s", utc=True)
                 .tz_convert(tz).tz_localize(None).normalize())
        quote_row = chart["indicators"]["quote"][0]
        adj = chart["indicators"].get("adjclose", [{}])[0].get("adjclose")
        if adj is None:
            raise ValueError("Adjusted closes required")
        f = pd.DataFrame({
            "date": dates, "open": quote_row["open"], "high": quote_row["high"],
            "low": quote_row["low"], "close": quote_row["close"],
            "volume": quote_row["volume"], "adj_close": adj,
        })
        # Today is excluded even if Yahoo publishes an incomplete daily bar.
        f = f.loc[f["date"] < stamp.tz_convert(tz).tz_localize(None).normalize()]
        f = f.sort_values("date").reset_index(drop=True)
        if len(f) < 600:
            raise ValueError("Fewer than 600 complete long-history daily sessions")
        nums = f[["open", "high", "low", "close", "adj_close"]]
        if (f.date.duplicated().any() or nums.isna().any().any()
                or not np.isfinite(nums.to_numpy()).all()
                or (nums <= 0).any().any()
                or (f.high < f[["open", "close"]].max(axis=1)).any()
                or (f.low > f[["open", "close"]].min(axis=1)).any()):
            raise ValueError("Bad OHLC/adjustments or duplicate dates")
        calendar = xcals.get_calendar("XNYS")
        start, end = f.date.iloc[0], f.date.iloc[-1]
        expected = calendar.sessions_in_range(start, end).tz_localize(None)
        actual = pd.DatetimeIndex(f.date)
        missing = expected.difference(actual)
        unexpected = actual.difference(expected)
        if len(missing) or len(unexpected):
            raise ValueError(f"Historical session mismatch ({len(missing)} missing, {len(unexpected)} unexpected)")
        return f, {"source": "Yahoo Finance", "price_status": "VALID",
                   "retrieved_at": retrieved.isoformat(),
                   "source_url": record.get("source_url"),
                   "observed_at": str(f.date.iloc[-1].date()),
                   "bars": len(f), "calendar": "XNYS exchange_calendars"}
    except (ImportError, ValueError, TypeError, IndexError, KeyError, AttributeError, OverflowError) as exc:
        return empty, {**meta, "price_status": "DEGRADED",
                       "retrieved_at": retrieved.isoformat(),
                       "reason": f"Long-history validation failed: {type(exc).__name__}: {str(exc)[:160]}"}


def evaluate_long_cached(root, symbols, *, as_of=None, fee_bps=10.0):
    stamp = _utc(as_of or datetime.now(timezone.utc))
    if stamp is None:
        raise ValueError("timezone-aware as_of required")
    results = []
    for symbol in dict.fromkeys(symbols):
        record = load_long_snapshot(root, symbol)
        if record is None:
            results.append(_abstain(symbol, "NO_LONG_SNAPSHOT", "Acquire the 5y-10y research cache first"))
            continue
        bars, meta = normalize_long_snapshot(record, symbol, as_of=stamp)
        if meta.get("price_status") != "VALID":
            results.append(_abstain(symbol, "UNQUALIFIED_LONG_HISTORY", meta["reason"]))
            continue
        results.append(evaluate_history(symbol, bars, meta, as_of=stamp, fee_bps=fee_bps))
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of": stamp.isoformat(), "model_version": VERSION,
            "purpose": "Research on independent 5y-10y calendar-audited public snapshots",
            "portfolio_data_included": False, "results": results}
