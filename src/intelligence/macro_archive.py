"""Versioned, source-backed FRED snapshot archive for offline/hosted macro research.

Only observations actually acquired from the FRED provider are preserved.
Archive latest is not proof of current source availability or vintage correctness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .macro import SERIES, macro_context
from .store import Store
from .report_export import atomic_json

SCHEMA_VERSION = "fred-published-cache.v1"
RAW_ARCHIVE_URL = (
    "https://raw.githubusercontent.com/simfed78/"
    "Market-Intelligence-Operations-Console/research-data/"
    "exports/research/macro_latest.json"
)


def _dt(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _usable(record, now):
    """Verify hash, semantic series and retrieval time; never manufacture values."""
    if not isinstance(record, dict):
        return False
    code = str(record.get("symbol", "")).removeprefix("FRED:")
    if (code not in SERIES or record.get("symbol") != "FRED:" + code
            or record.get("source") != "FRED" or record.get("kind") != "macro"):
        return False
    if not str(record.get("source_url", "")).startswith((
        "https://fred.stlouisfed.org/", "https://api.stlouisfed.org/"
    )):
        return False
    retrieved = _dt(record.get("retrieved_at"))
    if retrieved is None or retrieved > now:
        return False
    payload = record.get("payload")
    if not isinstance(payload, str) or len(payload) > 2_000_000:
        return False
    if not payload.startswith(f"observation_date,{code}\n"):
        return False
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != record.get("sha256"):
        return False
    try:
        observations = macro_context({"FRED:" + code: record}, now.isoformat())["observations"]
        row = observations.loc[observations.series.eq(code)]
        return len(row) == 1 and row.value.notna().all()
    except (KeyError, ValueError, TypeError, IndexError):
        return False


def _archive_records(data, now):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return {}
    records = data.get("records")
    if not isinstance(records, list) or len(records) > len(SERIES):
        return {}
    result = {}
    for record in records:
        if not _usable(record, now):
            continue
        if record["symbol"] in result:
            return {}
        result[record["symbol"]] = record
    return result


def build_archive(root, *, now=None):
    now = _dt(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Timezone-aware now required")
    snapshots = Store(Path(root)).latest_snapshots(as_of=now.isoformat())
    records = [record for symbol, record in sorted(snapshots.items())
               if symbol.startswith("FRED:") and _usable(record, now)]
    return {"schema_version": SCHEMA_VERSION, "assembled_at": now.isoformat(),
            "records": records}


def merge_archive(previous, incoming, *, now=None):
    """Never replace known good data with a timeout or an older observation."""
    now = _dt(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Timezone-aware now required")
    old = _archive_records(previous, now)
    new = _archive_records(incoming, now)
    merged = dict(old)
    for symbol, record in new.items():
        prior = merged.get(symbol)
        if prior is None:
            merged[symbol] = record
            continue
        current = macro_context({symbol: record}, now.isoformat())["observations"]
        previous_view = macro_context({symbol: prior}, now.isoformat())["observations"]
        current_day = str(current.loc[current.series.eq(symbol[5:]), "observed_at"].iloc[0])
        previous_day = str(previous_view.loc[previous_view.series.eq(symbol[5:]), "observed_at"].iloc[0])
        if (current_day, record["retrieved_at"]) > (previous_day, prior["retrieved_at"]):
            merged[symbol] = record
    return {"schema_version": SCHEMA_VERSION, "assembled_at": now.isoformat(),
            "records": [merged[key] for key in sorted(merged)]}


def bootstrap_public_macro(root, *, url=RAW_ARCHIVE_URL):
    """One bounded public HTTPS read. Source downtime cannot erase stored data."""
    try:
        request = Request(url, headers={"User-Agent": "TradingDesk-ReadOnly/1.0"})
        with urlopen(request, timeout=7) as response:
            raw = response.read(12_000_001)
        if len(raw) > 12_000_000:
            raise ValueError("Published macro archive exceeds maximum size")
        data = json.loads(raw.decode("utf-8"))
        accepted = _archive_records(data, datetime.now(timezone.utc))
        if not accepted:
            return {"status": "UNAVAILABLE", "imported": 0}
        store = Store(root)
        for item in accepted.values():
            store.put_snapshot(**{k: item[k] for k in
                                  ("symbol", "retrieved_at", "source",
                                   "source_url", "kind", "sha256", "payload")})
        return {"status": "ARCHIVED", "imported": len(accepted)}
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"status": "UNAVAILABLE", "imported": 0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.candidate is None:
        data = build_archive(args.root, now=now)
        if data["records"]:
            atomic_json(args.output, data)
        print(json.dumps({"new_records": len(data["records"])}))
        return 0
    old = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous and args.previous.exists() else {}
    new = json.loads(args.candidate.read_text(encoding="utf-8")) if args.candidate.exists() else {}
    result = merge_archive(old, new, now=now)
    if result["records"]:
        atomic_json(args.output, result)
    print(json.dumps({"published_records": len(result["records"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
