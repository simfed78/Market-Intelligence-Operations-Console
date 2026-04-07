"""Shared data adapters for the local dashboard and API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.models.signal_registry import load_rank_transitions, load_score_history
from src.storage.run_history import RunHistoryStore


DEFAULT_PAYLOAD_KEYS = [
    "alerts_table",
    "watchlist_table",
    "opportunity_table",
    "macro_event_table",
    "earnings_watch_table",
    "sector_internals_table",
    "options_context_table",
    "basket_tables",
    "transition_table",
    "run_history_table",
    "exposure_view",
    "portfolio_summary",
    "change_log",
]


def load_payload(project_root: Path, weekly: bool = False) -> dict[str, Any]:
    """Load the latest persisted payload."""
    name = "weekly_payload.json" if weekly else "daily_payload.json"
    path = project_root / "outputs" / "json" / name
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in DEFAULT_PAYLOAD_KEYS:
        payload.setdefault(key, [] if key.endswith("_table") else ({} if key in {"basket_tables", "exposure_view", "portfolio_summary", "change_log"} else []))
    return payload


def frame_from_payload(payload: dict[str, Any], key: str) -> pd.DataFrame:
    """Convert a payload list field to a DataFrame."""
    rows = payload.get(key, [])
    return pd.DataFrame(rows) if isinstance(rows, list) else pd.DataFrame()


def load_run_history(project_root: Path, limit: int = 30) -> pd.DataFrame:
    """Load persisted run history."""
    rows = RunHistoryStore(project_root).runs.run_history(limit=limit)
    return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


def load_latest_baskets(project_root: Path, weekly: bool = False) -> dict[str, pd.DataFrame]:
    """Load latest basket tables from the payload."""
    payload = load_payload(project_root, weekly=weekly)
    baskets = payload.get("basket_tables", {})
    if not isinstance(baskets, dict):
        return {}
    return {name: pd.DataFrame(rows) for name, rows in baskets.items() if isinstance(rows, list)}


def load_alert_history(project_root: Path, limit: int = 100) -> pd.DataFrame:
    """Load historical alerts from SQLite."""
    from src.storage.db import get_connection

    with get_connection(project_root) as conn:
        rows = conn.execute(
            """
            SELECT alerts.level, alerts.category, alerts.item, alerts.message, alerts.score, runs.timestamp
            FROM alerts
            JOIN runs ON runs.id = alerts.run_id
            ORDER BY alerts.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def load_score_history_frame(project_root: Path, score_name: str) -> pd.DataFrame:
    """Load historical score rows."""
    return load_score_history(project_root, score_name)


def load_transition_history(project_root: Path, limit: int = 100) -> pd.DataFrame:
    """Load transition rows."""
    return load_rank_transitions(project_root, limit=limit)


def load_what_changed(project_root: Path, weekly: bool = False) -> dict[str, Any]:
    """Assemble a concise what-changed view."""
    payload = load_payload(project_root, weekly=weekly)
    transitions = frame_from_payload(payload, "transition_table")
    return {
        "change_log": payload.get("change_log", {}),
        "transitions": transitions,
        "latest_run_history": frame_from_payload(payload, "run_history_table"),
    }
