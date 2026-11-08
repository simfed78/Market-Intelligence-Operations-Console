"""Publish a fail-closed, derived-only research brief for the weekly Trading Desk.

Reads only the completed Market Intelligence run. No broker, Core, local account
state, raw OHLC/volume bars, credentials or execution capability is exported.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

from .opportunities import HORIZONS, MODEL_VERSION, top10
from .service import load_dashboard

SCHEMA_VERSION = "research-brief.v1"
# Explicit public research proxies used by the limited Fineco workspace.
# None is an account holding, broker-order symbol, or confirmed EU UCITS listing.
FINECO_RESEARCH_PROXIES = ("VT", "ACWI", "GLD", "IAU", "USO", "DBC", "XLV", "XLP")
MIN_VALID_RATIO = 0.70
MAX_RUN_AGE_HOURS = 12
# Strict allowlist: no broker identifiers, raw provider payloads, or price history.
ASSET_FIELDS = (
    "symbol", "name", "asset_class", "subcategory", "region", "kind",
    "currency", "horizon", "model_version", "signal_state",
    "technical_score", "opportunity_score", "rank", "rank_change",
    "risk_score", "risk_category", "timing_score", "momentum_1m",
    "momentum_3m", "momentum_6m", "momentum_12m", "rs_21", "rs_63",
    "early_opportunity", "data_confidence", "price_status",
    "volume_status", "peer_count", "observed_at", "retrieved_at", "source",
)


def _parse_utc(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp privo di fuso orario")
    return parsed.astimezone(timezone.utc)


def _safe(value):
    """Convert pandas/numpy scalar values to finite, serializable primitives."""
    if value is None:
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, TypeError, AttributeError):
            pass
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value[:180]
    return None  # No arbitrary object repr, URLs, or opaque payloads.


def _asset(row):
    return {field: _safe(row.get(field)) for field in ASSET_FIELDS}


def build_brief(data, *, now=None):
    """Validate and assemble a snapshot; raise instead of publishing stale data."""
    now = _parse_utc(now or datetime.now(timezone.utc))
    latest = data.get("latest_run")
    if not isinstance(latest, dict) or not latest.get("run_at"):
        raise ValueError("Nessun run completo: export bloccato")
    run_at = _parse_utc(latest["run_at"])
    age_hours = (now - run_at).total_seconds() / 3600
    if age_hours < 0 or age_hours > MAX_RUN_AGE_HOURS:
        raise ValueError("Run non recente o con timestamp futuro: export bloccato")
    if int(latest.get("acquired", 0)) + int(latest.get("cached", 0)) == 0:
        raise ValueError("Nessuna acquisizione o cache qualificata nel run")

    metrics = data.get("metrics")
    if metrics is None or metrics.empty or "price_status" not in metrics:
        raise ValueError("Metriche assenti: export bloccato")
    valid_count = int(metrics.price_status.eq("VALID").sum())
    total = len(metrics)
    valid_ratio = valid_count / total
    if valid_ratio < MIN_VALID_RATIO:
        raise ValueError(f"Copertura insufficiente {valid_count}/{total}: export bloccato")

    horizons = {}
    for horizon in HORIZONS:
        ranked = data.get("opportunities", {}).get(horizon)
        if ranked is None or ranked.empty:
            raise ValueError(f"Ranking {horizon} assente: export bloccato")
        allowed = ranked[
            ranked.signal_state.isin(["RESEARCH CANDIDATE", "WATCHLIST"])
            & ranked.opportunity_score.notna()
            & ranked.price_status.eq("VALID")
        ].copy()
        if allowed.empty:
            raise ValueError(f"Nessun candidato qualificato su {horizon}")
        global_top = top10(ranked)
        class_leaders = {}
        for group, frame in allowed.groupby("asset_class", sort=True):
            class_leaders[str(group)] = [
                _asset(row) for row in
                frame.sort_values(["rank", "symbol"]).head(5).to_dict("records")
            ]
        horizons[horizon] = {
            "top10": [_asset(row) for row in global_top.to_dict("records")],
            "leaders_by_asset_class": class_leaders,
            "fineco_proxies": [_asset(row) for row in ranked[
                ranked.symbol.isin(FINECO_RESEARCH_PROXIES)
            ].sort_values("symbol").to_dict("records")],
            "eligible_count": len(allowed),
        }

    brief = {
        "schema_version": SCHEMA_VERSION,
        "mode": "RESEARCH_ONLY",
        "publication_status": "QUALIFIED_RESEARCH",
        "generated_at": now.isoformat(),
        "completed_run_at": run_at.isoformat(),
        "model_version": MODEL_VERSION,
        "quality": {
            "price_valid": valid_count,
            "instruments_total": total,
            "valid_ratio": round(valid_ratio, 4),
            "source_errors": len(latest.get("errors") or []),
            "macro_status": _safe((data.get("macro") or {}).get("status")) or "MISSING",
        },
        "horizons": horizons,
        "limitations": [
            "Ranking tecnico relativo, non previsione del rendimento a 12 mesi.",
            "Nessun segnale ENTRY validato; non usare come ordine BUY o SELL.",
            "Nessuna verifica di negoziabilita, UCITS/ETC, costi, spread o idoneita personale.",
            "Snapshot da fonti pubbliche indicative; dati non garantiti per execution.",
            "Nessun dato di conti Fineco/eToro, Core o serie storiche dei provider.",
        ],
    }
    # No NaN/Infinity, no arbitrary nested records, exact deterministic serialization.
    json.dumps(brief, allow_nan=False, ensure_ascii=False)
    return brief


def atomic_json(path, brief):
    """Do not damage the previous qualified export on an I/O failure."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(brief, ensure_ascii=False, allow_nan=False,
                         indent=2, sort_keys=True) + "\n"
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=".research-", suffix=".tmp", delete=False,
        ) as file:
            temp = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        temp.replace(target)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history-dir", type=Path)
    args = parser.parse_args(argv)
    data = load_dashboard(args.root)
    brief = build_brief(data)
    atomic_json(args.output, brief)
    if args.history_dir is not None:
        day = brief["completed_run_at"][:10]
        atomic_json(args.history_dir / f"{day}.json", brief)
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "run_at": brief["completed_run_at"],
        "price_valid": brief["quality"]["price_valid"],
        "path": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
