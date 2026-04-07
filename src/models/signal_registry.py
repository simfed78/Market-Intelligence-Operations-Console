"""Historical signal registry and transitions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.storage.run_history import RunHistoryStore


def build_state_transitions(previous: pd.DataFrame, current: pd.DataFrame, item_col: str = "ticker", label_col: str = "opportunity_label") -> pd.DataFrame:
    """Compare previous and current ranking states."""
    if previous.empty or current.empty:
        return pd.DataFrame()
    merged = previous[[item_col, label_col]].merge(
        current[[item_col, label_col]],
        how="inner",
        on=item_col,
        suffixes=("_prev", "_curr"),
    )
    changed = merged[merged[f"{label_col}_prev"] != merged[f"{label_col}_curr"]].copy()
    if changed.empty:
        return pd.DataFrame()
    changed["transition_type"] = label_col
    changed["previous_value"] = changed[f"{label_col}_prev"]
    changed["current_value"] = changed[f"{label_col}_curr"]
    changed["item"] = changed[item_col]
    changed["summary"] = changed.apply(lambda row: f"{row[item_col]} moved from {row['previous_value']} to {row['current_value']}.", axis=1)
    return changed[["item", "transition_type", "previous_value", "current_value", "summary"]]


def load_score_history(project_root: Path, score_name: str) -> pd.DataFrame:
    """Load score history from SQLite."""
    return RunHistoryStore(project_root).signals.history_scores(score_name)


def load_rank_transitions(project_root: Path, limit: int = 100) -> pd.DataFrame:
    """Load persisted transitions."""
    return RunHistoryStore(project_root).signals.rank_transitions(limit=limit)
