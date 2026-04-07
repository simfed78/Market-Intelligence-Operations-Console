"""Change-log helpers."""

from __future__ import annotations

import pandas as pd

from src.models.signal_registry import build_state_transitions


def build_change_summary(previous_opportunities: pd.DataFrame, current_opportunities: pd.DataFrame, previous_validation: pd.DataFrame, current_validation: pd.DataFrame) -> tuple[dict[str, str], pd.DataFrame]:
    """Create a small what-changed summary and transition table."""
    transitions = build_state_transitions(previous_opportunities, current_opportunities)
    summary: dict[str, str] = {}
    if not transitions.empty:
        summary["ranking_transitions"] = "; ".join(transitions["summary"].head(5).tolist())
    if not previous_validation.empty and not current_validation.empty:
        prev = previous_validation.groupby("proxy")["stability_score"].mean()
        curr = current_validation.groupby("proxy")["stability_score"].mean()
        aligned = pd.concat([prev.rename("prev"), curr.rename("curr")], axis=1).dropna()
        deteriorating = aligned.sort_values("curr").head(3)
        if not deteriorating.empty:
            summary["proxy_deterioration"] = ", ".join(f"{idx} {row['prev']:.1f}->{row['curr']:.1f}" for idx, row in deteriorating.iterrows())
    return summary, transitions
