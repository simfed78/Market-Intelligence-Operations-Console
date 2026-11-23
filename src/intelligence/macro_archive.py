"""A derived-only macro publication. No FRED raw observations are redistributed.

The scheduled research producer can privately read provider histories; the public
research-data branch stores only derived regime commentary, freshness metadata,
source URLs and input hashes. Copyrighted ICE BofA values are never published.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from .macro import SERIES, macro_context
from .report_export import atomic_json
from .store import Store

SCHEMA_VERSION = "macro-research-summary.v1"
ARCHIVE_URL = (
    "https://raw.githubusercontent.com/simfed78/"
    "Market-Intelligence-Operations-Console/research-data/"
    "exports/research/macro_latest.json"
)
LOCAL_COPY = Path("data/processed/macro_published_summary.json")


def _utc(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _digest(document):
    payload = {k: v for k, v in document.items() if k != "integrity_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()


def _valid(document, *, now=None):
    now = _utc(now) if now is not None else datetime.now(timezone.utc)
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        return False
    compiled = _utc(document.get("compiled_at"))
    if compiled is None or now is None or compiled > now:
        return False
    if document.get("integrity_sha256") != _digest(document):
        return False
    observations = document.get("observations")
    if not isinstance(observations, list) or not observations or len(observations) > len(SERIES):
        return False
    seen = set()
    for item in observations:
        if not isinstance(item, dict):
            return False
        code = item.get("series")
        if code not in SERIES or code in seen:
            return False
        seen.add(code)
        observed, acquired = item.get("observed_at"), _utc(item.get("retrieved_at"))
        if not isinstance(observed, str) or len(observed) != 10 or acquired is None:
            return False
        try:
            day = datetime.fromisoformat(observed).date()
        except ValueError:
            return False
        if day > now.date() or acquired > now or acquired.date() < day:
            return False
        if item.get("source_url") != f"https://fred.stlouisfed.org/series/{code}":
            return False
        if not isinstance(item.get("input_sha256"), str) or len(item["input_sha256"]) != 64:
            return False
        if "value" in item or "payload" in item or "api_key" in item:
            return False
    derived = document.get("derived_regime")
    if not isinstance(derived, dict):
        return False
    if derived.get("label") is not None and (not isinstance(derived["label"], str) or len(derived["label"]) > 160):
        return False
    if derived.get("reason") is not None and (not isinstance(derived["reason"], str) or len(derived["reason"]) > 750):
        return False
    if any(k not in {"label", "reason", "observation_time"} for k in derived):
        return False
    return True


def build_archive(root, *, now=None):
    """Compile derived facts from genuine, hash-checked FRED snapshots."""
    now = _utc(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Timezone-aware now required")
    snapshots = Store(Path(root)).latest_snapshots(as_of=now.isoformat())
    result = macro_context(snapshots, now.isoformat())
    observations = []
    for row in result["observations"].to_dict("records"):
        code = row["series"]
        if (row.get("value") is None or pd.isna(row.get("value"))
                or row.get("observed_at") is None):
            continue
        original = snapshots.get("FRED:" + code)
        if not isinstance(original, dict) or original.get("source") != "FRED":
            continue
        observations.append({
            "series": code,
            "observed_at": row["observed_at"],
            "retrieved_at": row["retrieved_at"],
            # Always point to the official series page for historical values.
            "source_url": f"https://fred.stlouisfed.org/series/{code}",
            "input_sha256": original["sha256"],
        })
    derived = {
        "label": result["label"] if result["label"] != "Non disponibile" else None,
        "reason": result["reason"] if result["label"] != "Non disponibile" else None,
        "observation_time": now.isoformat(),
    }
    document = {"schema_version": SCHEMA_VERSION, "compiled_at": now.isoformat(),
                "observations": sorted(observations, key=lambda x: x["series"]),
                "derived_regime": derived}
    document["integrity_sha256"] = _digest(document)
    return document


def merge_archive(previous, incoming, *, now=None):
    """Outages retain previous dated observations, never replace them with blanks."""
    now = _utc(now) if now is not None else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("Timezone-aware now required")
    old = previous if _valid(previous, now=now) else {}
    new = incoming if _valid(incoming, now=now) else {}
    entries = {item["series"]: item for item in old.get("observations", [])}
    for item in new.get("observations", []):
        before = entries.get(item["series"])
        if before is None or (item["observed_at"], item["retrieved_at"]) > (
                before["observed_at"], before["retrieved_at"]):
            entries[item["series"]] = item
    newer_regime = new.get("derived_regime") or {}
    older_regime = old.get("derived_regime") or {}
    derived = newer_regime if newer_regime.get("label") else older_regime
    document = {"schema_version": SCHEMA_VERSION, "compiled_at": now.isoformat(),
                "observations": [entries[k] for k in sorted(entries)],
                "derived_regime": derived or {"label": None, "reason": None,
                                             "observation_time": now.isoformat()}}
    document["integrity_sha256"] = _digest(document)
    return document


def bootstrap_public_macro(root, *, url=ARCHIVE_URL):
    """Read-only Cloud bootstrap. No FRED network requests and no raw data."""
    try:
        request = Request(url, headers={"User-Agent": "TradingDesk-ReadOnly/1.0"})
        with urlopen(request, timeout=7) as response:
            raw = response.read(120_001)
        if len(raw) > 120_000:
            return {"status": "UNAVAILABLE", "imported": 0}
        document = json.loads(raw.decode("utf-8"))
        if not _valid(document):
            return {"status": "UNAVAILABLE", "imported": 0}
        atomic_json(Path(root) / LOCAL_COPY, document)
        return {"status": "ARCHIVED", "imported": len(document["observations"])}
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "UNAVAILABLE", "imported": 0}


def archived_macro_context(root, *, as_of=None):
    """Derived evidence only; stale observations cannot carry forward a regime."""
    now = _utc(as_of) if as_of is not None else datetime.now(timezone.utc)
    path = Path(root) / LOCAL_COPY
    try:
        if not path.exists() or path.stat().st_size > 120_000:
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
        if not _valid(document, now=now):
            return None
    except (OSError, ValueError):
        return None
    observations = []
    saved = {item["series"]: item for item in document["observations"]}
    for code, (name, unit, max_age) in SERIES.items():
        item = saved.get(code)
        observed = item["observed_at"] if item else None
        stale = ((now.date() - datetime.fromisoformat(observed).date()).days > max_age
                 if observed else None)
        observations.append({
            "series": code, "name": name, "unit": unit, "value": None,
            "observed_at": observed, "retrieved_at": item["retrieved_at"] if item else None,
            "available_at": item["retrieved_at"] if item else None,
            "source": "FRED", "source_url": f"https://fred.stlouisfed.org/series/{code}",
            "status": "ARCHIVED_METADATA" if item else "MISSING",
            "stale": stale, "vintage": "Revised latest; original release vintage not verified",
            "reason": ("Published indicator not redistributed; open source link"
                       if item else "No verified published indicator"),
        })
    fresh_macro = all(code in saved and (now.date() - datetime.fromisoformat(
        saved[code]["observed_at"]).date()).days <= SERIES[code][2]
                      for code in ("CPIAUCSL", "INDPRO"))
    derived = document["derived_regime"]
    label = derived.get("label") if fresh_macro and derived.get("label") else "Non disponibile"
    reason = (derived.get("reason") if label != "Non disponibile" else
              "Archived macro observations are incomplete/stale or regime derivation unavailable.")
    return {"label": label, "reason": reason, "status": "DEGRADED",
            "observations": pd.DataFrame(observations), "archived": True}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.candidate is None:
        result = build_archive(args.root, now=now)
    else:
        def read_optional(path):
            if not path or not path.exists() or not path.stat().st_size:
                return {}
            return json.loads(path.read_text(encoding="utf-8"))
        result = merge_archive(read_optional(args.previous),
                               read_optional(args.candidate), now=now)
    if result["observations"]:
        atomic_json(args.output, result)
    print(json.dumps({"published_indicators": len(result["observations"]),
                      "raw_values_published": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
