"""Watchlist report writers."""

from __future__ import annotations

import pandas as pd


def build_watchlist_markdown(alerts: pd.DataFrame, watchlist: pd.DataFrame) -> str:
    """Render watchlist markdown."""
    def table_md(frame: pd.DataFrame) -> str:
        return frame.to_markdown(index=False) if not frame.empty else "_No items._"

    return f"""# Daily Watchlist

## Alert Center
{table_md(alerts.head(12))}

## Opportunity Watchlist
{table_md(watchlist.head(12))}
"""
